# CogniTrace: The Context-Aware Debugger
State of the Art LLM-Powered Interactive Debugging Experience. CogniTrace represents a paradigm shift in developer productivity, moving the debugger from a state inspection tool to a context-aware reasoning partner. By tightly integrating a Large Language Model (LLM) into the standard Python debugging workflow (pdb), it eliminates the most time-consuming aspects of debugging: manually inspecting state, cross-referencing documentation, and formulating hypotheses.

## ⚡ Support
<div align="center">

**Made with ❤️ and ☕ by the Plantacerium**

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/plantacerium)

⭐ **Star us on GitHub** if the script is useful to You! ⭐
</div>

## Advanced Developer Productivity
In Situ Cognitive Assistance: Developers no longer have to copy code snippets, variables, or stack traces into a separate chat window. The LLM is invoked directly within the debugger environment ((Pdb) do ai ...), preserving mental flow and drastically reducing context-switching, the silent killer of productivity.

Zero-Configuration Local LLM Integration: By defaulting to a configurable API endpoint (OLLAMA_URL), CogniTrace promotes a secure, private, and low-latency debugging experience using local or private LLMs. This is essential for handling sensitive, proprietary source code without exposing it to third-party services.

Automated Crash Analysis (Post-Mortem): The handle_crash() function allows the debugger to automatically take control when an unhandled exception occurs (sys.exc_info()). It immediately spawns the LLM agent to analyze the full traceback, local variables, and code context, providing an instant root-cause analysis suggestion.

Context-Safe State Summarization: It intelligently summarizes large or complex data structures using reprlib and a configurable MAX_VAR_LEN, ensuring that massive variables don't exceed the LLM's context window, which is a critical failure point for other LLM-assisted tools.

## Key Advantages
⚡️ 10x Faster Root Cause Analysis: Ask the debugger why instead of just what. Get direct answers like, "The ZeroDivisionError is on line 12 because the threshold variable remained 0, as none of the data_points exceeded 100."

Reduced Cognitive Load: Offload the manual, repetitive work of tracing execution flow and checking variable types to your AI partner.

Instant Context-Aware Answers: Query the LLM about the state of local variables, the logic of a third-party library call, or common pitfalls of a function—all without leaving your terminal.

Secure & Private: Use your own local or private LLM instance, ensuring your proprietary source code never leaves your network.

Familiar Workflow: Built directly on the standard Python Debugger (pdb.Pdb), preserving muscle memory for Python developers.

| Feature | Description | Implementation Details (from `cognitrace.py`) |
| :--- | :--- | :--- |
| **PDB Extension** | Inherits all standard Python debugging commands (n, s, c, b) | Extends `pdb.Pdb` |
| **LLM Interaction** | Dedicated command to pose questions to the LLM | Implements the `do_ai` command |
| **Custom Configuration** | Allows specifying the LLM service endpoint and model | Configured via `Config` class, using `OLLAMA_URL` and `MODEL` (default: `qwen3:8b`) |
| **Safe Variable Handling** | Prevents context window overload from large objects | Uses `reprlib` with a `MAX_VAR_LEN` limit (default: 500 characters) |
| **Post-Mortem Mode** | Automatically analyzes exceptions/crashes | Implements `handle_crash()` using `sys.exc_info()` |
| **Hard Breakpoint** | Function to programmatically start the debugger | Implements `start_trace()` which calls `AIDebugAgent().set_trace()` |

## Usage
### Post-Mortem Crash Analysis (`handle_crash`)

Use `handle_crash()` inside a top-level `try...except` block to automatically launch the AI Debugger when an unhandled exception occurs. The debugger will spawn at the exact line where the exception was raised, allowing you to immediately run the `ai` command for a root cause analysis.

**Example Script (`app_with_crash_handler.py`):**

```python
from cognitrace import handle_crash
import sys

def process_data(data):
    """Contains a hidden bug."""
    divisor = 0
    for item in data:
        if item > 5:
            divisor += 1
    
    # This line will crash if 'data' contains no items > 5.
    result = 100 / (divisor - 1) 
    return result

if __name__ == "__main__":
    # Simulate a run with data that triggers the bug
    bad_data = [1, 2, 3] 

    try:
        process_data(bad_data)
    except Exception:
        # This function catches the exception and launches the AI Debugger
        # at the crash site for post-mortem analysis.
        print("Application crashed. Spawning AI Debugger...")
        handle_crash()

```

**Expected Interaction Flow:**

1.  The script runs and hits a `ZeroDivisionError`.
2.  The `except` block calls `handle_crash()`.
3.  The debugger launches.
4.  You can then type the **`ai`** command at the prompt:


```bash
$ python app_with_crash_handler.py
Application crashed. Spawning AI Debugger...
[AI-DEBUG WARN] Crash detected! Spawning AI Agent...
-> /path/to/app_with_crash_handler.py(14)process_data()
-> result = 100 / (divisor - 1) 
(Pdb-AI) ai

[AI-DEBUG] Connecting to http://localhost:11434/api/generate using model 'qwen3:8b'...

=== 🧠 AI DIAGNOSIS ===
Diagnosis: The code is raising a ZeroDivisionError because the variable 'divisor' is 1 (due to the loop logic) and the calculation is 1 / (1 - 1), resulting in division by zero.
Fix: Ensure 'divisor - 1' is never zero, or handle the edge case before the division.
Suggested Autonomous Commands:
 1. p divisor
 2. p divisor - 1
 3. q

=======================
(Pdb-AI) 
```

### Intentional Hard Breakpoint (`start_trace`)

Use `start_trace()` to programmatically set a breakpoint and drop into the debugger session at a specific line of code. This is useful for inspecting complex state before a critical function call.

**Example Script (`app_with_trace.py`):**

```python
from cognitrace import start_trace
from typing import Dict, Any

def configure_system(settings: Dict[str, Any]):
    """Configures the system based on provided settings."""
    final_settings = {"default_timeout": 60, **settings}
    
    # Inject a breakpoint here to analyze 'final_settings' 
    # and decide on the next step using the 'ai' command.
    start_trace() 
    
    print(f"System configured with: {final_settings}")

if __name__ == "__main__":
    user_settings = {"mode": "production", "log_level": "ERROR"}
    configure_system(user_settings)
```

**Expected Interaction Flow:**

1.  The script executes and reaches the `start_trace()` line.
2.  The debugger immediately takes control.
3.  You can then use standard PDB commands (like `p`, `n`, `c`) or the AI commands.


```bash
$ python app_with_trace.py
-> /path/to/app_with_trace.py(12)configure_system()
-> start_trace()
(Pdb-AI) p final_settings
{'default_timeout': 60, 'mode': 'production', 'log_level': 'ERROR'}
(Pdb-AI) ai What is the best log_level setting for production mode?

[AI-DEBUG] Connecting to http://localhost:11434/api/generate using model 'qwen3:8b'...

=== 🧠 AI DIAGNOSIS ===
Diagnosis: The current 'log_level' is ERROR, which is generally appropriate for production to avoid excessive logging overhead. If detailed error traces are needed for specific components, consider 'WARNING' or 'INFO' locally.
Fix: No change needed.
Suggested Autonomous Commands:
 1. n

=======================
(Pdb-AI) n
-> /path/to/app_with_trace.py(14)configure_system()
-> print(f"System configured with: {final_settings}")
(Pdb-AI) c
System configured with: {'default_timeout': 60, 'mode': 'production', 'log_level': 'ERROR'}
```

## ⚡ Support
<div align="center">

**Made with ❤️ and ☕ by the Plantacerium**

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/plantacerium)

⭐ **Star us on GitHub** if the script is useful to You! ⭐
</div>
