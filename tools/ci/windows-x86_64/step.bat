@echo off

:: Veify formatting
call "%~dp0..\..\..\format_code.bat" --verify
if %errorlevel% neq 0 ( exit /b %errorlevel% )

:: Full rebuild
call "%~dp0..\..\..\build.bat" -x
if %errorlevel% neq 0 ( exit /b %errorlevel% )

:: Docs
call "%~dp0..\..\build_docs.bat" -c release
if %errorlevel% neq 0 ( exit /b %errorlevel% )

:: Run python tests (TODO: fix or remove)
::call "%~dp0..\..\test_runner.bat" --suite pythontests --config debug
::if %errorlevel% neq 0 ( exit /b %errorlevel% )

:: Run kit tests 
:: SKIP THEM for now, that puts a hard requirement on TC agent (to have RTX, driver version, etc.)
::call "%~dp0..\..\test_runner.bat" --suite kittests --config release
::if %errorlevel% neq 0 ( exit /b %errorlevel% )

:: Package
call "%~dp0..\..\package.bat"
if %errorlevel% neq 0 ( exit /b %errorlevel% )

:: publish artifacts to teamcity
echo ##teamcity[publishArtifacts '_build/packages']


