# Configuration file - Files section

Location of the log file and state data retention.

| Key | Description |
|:--|:--|
| LogfileName | A text log file that records progress messages and warnings. |
| LogProcessID | If True, include the process ID in the log entries. |
| LogfileMaxLines | Maximum number of lines to keep in the log file. If zero, the file will never be truncated. |
| LogfileVerbosity | The level of detail captured in the log file. One of: none; error; warning; summary; detailed; debug; all. |
| ConsoleVerbosity | Controls the amount of information written to the console. One of: error; warning; summary; detailed; debug. Errors are written to stderr, all other messages are written to stdout. |
| DeleteOldStateFiles | Delete state data files older than this many hours (maximum 168). Set to 0 or blank to disable deletion. |
