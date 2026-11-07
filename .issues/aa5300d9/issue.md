# noisy tests

Sample:

```
(.venvpy3) C:\code\ai_llm\issue_tracker_todo.txt>py -3 test_todo.py
Created issue [9022789e] 'Fix critical login bug'
.Created issue [24070bde] 'First issue'
Created issue [6ce84c41] 'Second issue'
Error: No issue found matching hash prefix 'nonexistent'
.Created issue [341ef45f] 'Update documentation for API endpoints'
Closed and archived issue [341ef45f]
.Created issue [ee22594e] 'Refactor database connection pool'
Added comment to ee22594e as 20261106_2203.md
.
----------------------------------------------------------------------
Ran 4 tests in 0.065s

OK

(.venvpy3) C:\code\ai_llm\issue_tracker_todo.txt>py -2 test_todo.py
Created issue [482bc7a3] 'Fix critical login bug'
.Created issue [9722c2d2] 'First issue'
Created issue [969ecf77] 'Second issue'
Error: No issue found matching hash prefix 'nonexistent'
.Created issue [ebf4ea9c] 'Update documentation for API endpoints'
Closed and archived issue [ebf4ea9c]
.Created issue [f9d59318] 'Refactor database connection pool'
Added comment to f9d59318 as 20261106_2203.md
.
----------------------------------------------------------------------
Ran 4 tests in 0.073s

OK
```
