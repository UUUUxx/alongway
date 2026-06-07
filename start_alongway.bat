@echo off
setlocal

set "ARGS="

:parse_args
if "%~1"=="" goto run_script

if /I "%~1"=="stop" (
  set "ARGS=%ARGS% -Stop"
  shift
  goto parse_args
)
if /I "%~1"=="-stop" (
  set "ARGS=%ARGS% -Stop"
  shift
  goto parse_args
)
if /I "%~1"=="/stop" (
  set "ARGS=%ARGS% -Stop"
  shift
  goto parse_args
)

if /I "%~1"=="skipinstall" (
  set "ARGS=%ARGS% -SkipInstall"
  shift
  goto parse_args
)
if /I "%~1"=="-skipinstall" (
  set "ARGS=%ARGS% -SkipInstall"
  shift
  goto parse_args
)
if /I "%~1"=="/skipinstall" (
  set "ARGS=%ARGS% -SkipInstall"
  shift
  goto parse_args
)

if /I "%~1"=="env" (
  set "ARGS=%ARGS% -EnvName %~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="-env" (
  set "ARGS=%ARGS% -EnvName %~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="/env" (
  set "ARGS=%ARGS% -EnvName %~2"
  shift
  shift
  goto parse_args
)

set "ARGS=%ARGS% %1"
shift
goto parse_args

:run_script
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_alongway.ps1" %ARGS%

endlocal
