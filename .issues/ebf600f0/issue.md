# edit doesn't work

All sorts of errors:

```
(.venvpy3) C:\code\ai_llm\issue_tracker_todo.txt>py -3 todo.py add "noisy tests"
Created issue [aa5300d9] 'noisy tests'

(.venvpy3) C:\code\ai_llm\issue_tracker_todo.txt>py -3 todo.py edit "noisy tests"
Error: No issue found matching hash prefix 'noisy tests'

(.venvpy3) C:\code\ai_llm\issue_tracker_todo.txt>py -3 todo.py list

--- Open Issues (todo.txt) ---

 1: 2026-11-06 noisy tests hash:aa5300d9


(.venvpy3) C:\code\ai_llm\issue_tracker_todo.txt>py -3 todo.py edit 1
Error: No issue found matching hash prefix '1'

(.venvpy3) C:\code\ai_llm\issue_tracker_todo.txt>py -3 todo.py edit "aa5300d9"
Error launching editor 'nano': [WinError 2] The system cannot find the file specified
```
