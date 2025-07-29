# Step 1: Get custom token from your FastAPI endpoint
$customToken = (Invoke-RestMethod -Uri "http://localhost:8000/create-custom-token?user_id=asdf" -Method Post -ContentType "application/json").custom_token

# Step 2: Exchange for ID token with emulator
$response = Invoke-RestMethod -Uri "http://localhost:9099/www.googleapis.com/identitytoolkit/v3/relyingparty/verifyCustomToken?key=fake-api-key" -Method Post -Body (@{
    token = $customToken
    returnSecureToken = $true
} | ConvertTo-Json) -ContentType "application/json"
Write-Host "custom token: $($customToken)"
Write-Host "ID Token: $($response.idToken)"