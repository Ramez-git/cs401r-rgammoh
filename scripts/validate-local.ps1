# Windows equivalent of make local-validate LOCAL_OUT=docs/lab2-localstack-output.txt.
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
function Invoke-LocalAws {
    param([string[]]$Arguments)
    Invoke-Checked 'aws' (@('--endpoint-url', 'http://localhost:4566', '--region', 'us-east-1') + $Arguments)
}
# Scope emulator credentials to this script invocation and restore the caller.
$previousAccess = $env:AWS_ACCESS_KEY_ID
$previousSecret = $env:AWS_SECRET_ACCESS_KEY
$previousToken = $env:AWS_SESSION_TOKEN
try {
$env:AWS_ACCESS_KEY_ID = 'test'
$env:AWS_SECRET_ACCESS_KEY = 'test'
$env:AWS_SESSION_TOKEN = $null
& {
    Write-Output 'NorthStar Lab 2 - LocalStack validation'
    Invoke-Checked 'docker' @('compose', 'up', '-d', '--wait')
    Invoke-Checked 'terraform' @('-chdir=infrastructure/environments/local', 'init', '-input=false', '-no-color')
    Invoke-Checked 'terraform' @('-chdir=infrastructure/environments/local', 'apply', '-auto-approve', '-input=false', '-no-color')
    Invoke-LocalAws @('sts', 'get-caller-identity')
    $localBucket = Invoke-Checked 'terraform' @('-chdir=infrastructure/environments/local', 'output', '-raw', 's3_bucket_name')
    Invoke-LocalAws @('s3', 'ls', "s3://$localBucket/", '--recursive')
    $localRoles = Invoke-LocalAws @('iam', 'list-roles', '--query', 'Roles[*].RoleName', '--output', 'json')
    Write-Output $localRoles
    foreach ($roleName in @('MLEngineer', 'DataEngineer', 'ModelMonitor')) {
        if (($localRoles | ConvertFrom-Json) -notcontains "northstar-local-$roleName") { throw "Missing role $roleName" }
    }
    Invoke-LocalAws @('ec2', 'describe-vpcs', '--query', 'Vpcs[*].{Id:VpcId,CIDR:CidrBlock}')
    Invoke-LocalAws @('ec2', 'describe-subnets', '--query', 'Subnets[*].{Id:SubnetId,CIDR:CidrBlock}')
    $localNats = Invoke-LocalAws @('ec2', 'describe-nat-gateways', '--query', 'NatGateways[*].NatGatewayId', '--output', 'json')
    Write-Output "NAT gateways (expected none): $localNats"
    if (($localNats | ConvertFrom-Json).Count -ne 0) { throw 'Unexpected LocalStack NAT' }
    Write-Output 'PASS: LocalStack validation complete'
} 2>&1 | Tee-Object -FilePath docs/lab2-localstack-output.txt
} finally {
    $env:AWS_ACCESS_KEY_ID = $previousAccess
    $env:AWS_SECRET_ACCESS_KEY = $previousSecret
    $env:AWS_SESSION_TOKEN = $previousToken
}
