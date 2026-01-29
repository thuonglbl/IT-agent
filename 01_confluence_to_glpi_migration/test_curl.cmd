@echo off
echo Testing GLPI Connection with CURL...
echo.

curl.exe -v -k -X GET "https://your-glpi-instance/api.php/v1/initSession" -H "App-Token: YOUR_APP_TOKEN" -H "Authorization: user_token YOUR_USER_TOKEN"

echo.
pause
