@echo off
setlocal enabledelayedexpansion

:: --- Configuration ---
set "FastApiBaseUrl=http://127.0.0.1:8000"
set "FirebaseAuthEmulatorUrl=http://127.0.0.1:9099"
set "FirebaseAuthEmulatorPath=identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
set "TargetUid=gowVFUpCAnhZXApeu2EhSFrBSa1i"

:: --- Step 1: Get Custom Token from FastAPI ---
echo Requesting custom token for UID "%TargetUid%" from FastAPI...
curl -s "%FastApiBaseUrl%/generateCustomToken?uid=%TargetUid%" -H "Content-Type: application/json" -o token.json

if not exist token.json (
    echo [ERROR] Failed to retrieve custom token. FastAPI might not be running.
    exit /b 1
)

:: Extract custom token from JSON (very basic parsing)
set "CustomToken="
for /f "tokens=2 delims=:," %%A in ('findstr /i "customToken" token.json') do (
    set "CustomToken=%%~A"
    set "CustomToken=!CustomToken:~1,-1!"
)
del token.json

if not defined CustomToken (
    echo [ERROR] Custom token not found in response.
    exit /b 1
)

echo [INFO] Received Custom Token:
echo !CustomToken!
echo.

:: --- Step 2: Exchange Custom Token with Firebase Auth Emulator ---
set "RequestUrl=%FirebaseAuthEmulatorUrl%/%FirebaseAuthEmulatorPath%"

echo [INFO] Exchanging custom token with Firebase Auth Emulator...
(
  echo {
  echo   "token": "!CustomToken!",
  echo   "returnSecureToken": true
  echo }
) > body.json


curl -s -X POST "%RequestUrl%" ^
     -H "Authorization: Bearer owner" ^
     -H "Content-Type: application/json" ^
     -d @body.json -o response.json

:: Show raw response
echo.
echo [INFO] Raw Response from Emulator:
type response.json
echo.

:: Parse and display values
set "idToken="
set "refreshToken="
set "expiresIn="

for /f "tokens=1,* delims=," %%A in (response.json) do (
    echo %%A | findstr /c:"idToken" >nul && set "idToken=%%A"
    echo %%A | findstr /c:"refreshToken" >nul && set "refreshToken=%%A"
    echo %%A | findstr /c:"expiresIn" >nul && set "expiresIn=%%A"
)

echo --- Exchange Successful ---
echo ID Token: !idToken!
echo Refresh Token: !refreshToken!
echo Expires In: !expiresIn!
echo.

:: Clean up
del body.json
del response.json
