import sys
import pdb
import json
import os
import io
import requests
import traceback
import linecache
import reprlib  # Essential for production: handles massive objects safely
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# --- Configuration & Environment ---
@dataclass
class Config:
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    MODEL: str = os.getenv("AID_MODEL", "qwen3:8b")  # Default to a capable model
    CONTEXT_SIZE: int = int(os.getenv("AID_CONTEXT_SIZE", "4096"))
    # Safety: Limit variable size in logs to prevent blowing up the LLM context window
    MAX_VAR_LEN: int = 500 

config = Config()

# --- Utility: Safe Output ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log_info(msg): print(f"{Colors.OKCYAN}[AI-DEBUG]{Colors.ENDC} {msg}")
def log_warn(msg): print(f"{Colors.WARNING}[AI-DEBUG WARN]{Colors.ENDC} {msg}")
def log_err(msg): print(f"{Colors.FAIL}[AI-DEBUG ERROR]{Colors.ENDC} {msg}")

# --- Core Service: Ollama Integration ---

def query_ollama(prompt_context: dict, user_query: str) -> dict:
    """
    Sends a streamlined, production-optimized prompt to the local Ollama instance.
    """
    
    # Context Pruning: We only send what's necessary to save tokens/time
    system_prompt = (
        "You are an advanced Python Debugging Agent (Level 15). "
        "You have access to the current stack trace, local variables, and code snippet. "
        "Analyze the Root Cause and provide a Fix. "
        "If you need to verify assumptions, suggest specific Pdb commands. "
        "Response MUST be valid JSON with keys: 'diagnosis', 'suggested_fix', 'pdb_commands'."
    )

    full_prompt = f"""
    {system_prompt}
    
    --- SNAPSHOT ---
    Error: {prompt_context.get('exception_str', 'None')}
    Function: {prompt_context.get('function')}
    Line: {prompt_context.get('line_number')}
    Code Context:
    {prompt_context.get('source_code_snippet')}
    
    Variables:
    {json.dumps(prompt_context.get('local_variables'), indent=2)}
    
    --- USER QUERY ---
    {user_query}
    """

    payload = {
        "model": config.MODEL,
        "prompt": full_prompt,
        "stream": False,
        "format": "json", # Forces Ollama to output parseable JSON
        "options": {
            "num_ctx": config.CONTEXT_SIZE,
            "temperature": 0.2 # Low temp for analytical precision
        }
    }

    try:
        log_info(f"Connecting to {config.OLLAMA_URL} using model '{config.MODEL}'...")
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=480)
        response.raise_for_status()
        
        result_text = response.json().get("response", "")
        # Robust JSON parsing handling
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            # Fallback if model chats instead of returning JSON
            return {
                "diagnosis": result_text,
                "suggested_fix": "Could not parse specific fix from model output.",
                "pdb_commands": []
            }

    except requests.exceptions.ConnectionError:
        log_err("Could not connect to Ollama. Is it running? (run `ollama serve`)")
        return {"diagnosis": "Connection Error", "suggested_fix": "Start Ollama", "pdb_commands": []}
    except Exception as e:
        log_err(f"LLM Error: {e}")
        return {"diagnosis": f"Error: {str(e)}", "suggested_fix": "N/A", "pdb_commands": []}

# --- The Agent ---

class AIDebugAgent(pdb.Pdb):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Register the command alias 'ai' for ease of use
        self.prompt = f"{Colors.OKBLUE}(Pdb-AI){Colors.ENDC} "

    def do_ai(self, arg):
        """
        Usage: ai [query]
        Analyze the current state with the LLM. If no query is provided, performs a Root Cause Analysis.
        """
        user_query = arg.strip() or "Analyze the root cause of the current state/error."
        
        snapshot = self._capture_safe_context()
        
        log_info("Thinking... (Analyzing Stack & Variables)")
        analysis = query_ollama(snapshot, user_query)
        
        print(f"\n{Colors.HEADER}=== 🧠 AI DIAGNOSIS ==={Colors.ENDC}")
        print(f"{Colors.BOLD}Diagnosis:{Colors.ENDC} {analysis.get('diagnosis')}")
        print(f"{Colors.BOLD}Fix:{Colors.ENDC}       {analysis.get('suggested_fix')}")
        
        commands = analysis.get('pdb_commands', [])
        if commands:
            print(f"\n{Colors.WARNING}Suggested Autonomous Commands:{Colors.ENDC}")
            for i, cmd in enumerate(commands, 1):
                print(f" {i}. {cmd}")
            
            if self._confirm_action("Execute these commands autonomously?"):
                self._autonomous_drive(commands)
            else:
                log_info("Skipped autonomous commands.")
        
        print(f"{Colors.HEADER}======================={Colors.ENDC}\n")

    def _capture_safe_context(self) -> Dict[str, Any]:
        """
        Captures context using Reprlib for safe truncation and linecache
        for reliable source code retrieval.
        """
        frame = self.curframe
        code = frame.f_code
        lineno = frame.f_lineno
        filename = code.co_filename
        
        # 1. Safe Variable Extraction (FIX: Ensures local_vars is defined here)
        safe_repr = reprlib.Repr()
        # Ensure config is available or use a hardcoded value for max length
        max_var_len = getattr(self, 'config', type('obj', (object,), {'MAX_VAR_LEN': 500})()).MAX_VAR_LEN
        safe_repr.maxstring = max_var_len
        safe_repr.maxother = max_var_len
        
        # This line defines local_vars by safely representing the frame's local variables
        local_vars = {k: safe_repr.repr(v) for k, v in frame.f_locals.items()} 
        
        
        # 2. Source Code Window
        snippet = []
        try:
            # Load the file into linecache
            linecache.checkcache(filename)
            
            # Define the start and end lines for the context window
            start_line = max(1, lineno - 5)
            end_line = lineno + 5
            
            # Retrieve lines from linecache
            for i in range(start_line, end_line + 1):
                line = linecache.getline(filename, i)
                if line:
                    # Highlight the current line with an arrow for clarity
                    prefix = "--> " if i == lineno else "    "
                    snippet.append(f"{prefix}{i}: {line.rstrip()}")
                
        except Exception as e:
            # Log the source retrieval error, but don't crash the debugger
            # print(f"Warning: Could not retrieve source code for {filename}. Error: {e}", file=sys.stderr)
            snippet = [f"<Source not available for {filename}>"]
            
        snippet_str = "\n".join(snippet)

        # 3. Exception Info (if post-mortem)
        exc_info = sys.exc_info()
        exc_str = traceback.format_exception_only(exc_info[0], exc_info[1])[0].strip() if exc_info[0] else "Breakpoint (No Exception)"

        # 4. Return the full context (local_vars is now correctly defined)
        return {
            "function": code.co_name,
            "line_number": lineno,
            "local_variables": local_vars,  # <--- Defined in step 1
            "source_code_snippet": snippet_str,
            "exception_str": exc_str
        }

    def _confirm_action(self, text: str) -> bool:
        """Production safeguard: Human-in-the-loop confirmation."""
        response = input(f"{Colors.WARNING}⚠️  {text} [y/N]: {Colors.ENDC}")
        return response.strip().lower() == 'y'

    def _autonomous_drive(self, commands: List[str]):
        """Executes commands injected by the LLM."""
        log_info("Taking the wheel...")
        for cmd in commands:
            print(f"-> {cmd}")
            self.onecmd(cmd)

# --- Production Entry Point Helper ---

def start_trace():
    """Call this to hard-break into the AI Debugger anywhere in code."""
    AIDebugAgent().set_trace()

def handle_crash():
    """Call this in a try/except block to analyze a crash post-mortem."""
    # 1. Get the current exception info
    exc_type, exc_value, exc_tb = sys.exc_info()
    
    if exc_type:
        log_warn("Crash detected! Spawning AI Agent...")
        
        # 2. Instantiate the agent
        debugger = AIDebugAgent()
        
        # 3. Reset ensures clean state, then 'interaction' starts the session with the traceback
        debugger.reset()
        debugger.interaction(None, exc_tb)

# --- Example Usage (The "Buggy" App) ---


    # Test Function with an implicit bug (Division by Zero lurking)

def run_agent_test():
    """A self-contained test to verify the CogniTrace AIDebugAgent setup works."""
    def risky_calculation(data_points):
        threshold = 0
        total = 0
        for pt in data_points:
            # Bug: logic allows threshold to remain 0 if points are small
            if pt > 100:
                threshold += 1
            total += pt
        
        # This will crash if no points > 100
        result = total / threshold 
        return result

    print("Starting Production Simulation...")
    data = [10, 20, 50, 99]  # All below 100, so threshold stays 0
    try:
        risky_calculation(data)
    except Exception:
        handle_crash()

if __name__ == "__main__":
    run_agent_test()
