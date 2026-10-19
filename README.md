# Uptime Sentinel

A small serverless uptime and SSL expiry monitor I built on Azure. A Python Azure Function runs every minute, checks a list of URLs, and logs the status, latency and certificate days remaining to Application Insights. Everything is deployed with Bicep.

I built it as a hands-on Azure project. Monitoring and certificate expiry are things I've dealt with on the support side, so I wanted to build the tooling myself.

## What it does

- Checks each URL for HTTP status and response time
- Gets the SSL certificate expiry and warns when under 15 days remain
- Classifies each check as `UP` (2xx/3xx), `DEGRADED` (4xx/5xx) or `DOWN` (timeout or connection failure)
- Writes consistent log lines (`CHECK_RESULT`, `CHECK_FAILURE`, `SSL_WARNING`) that are easy to query with KQL
- Takes its target URLs from a Bicep parameter

## How it fits together

```
Timer trigger (every 60s)
        │
        ▼
Azure Function (Python 3.11, Linux Consumption)
        │
        ▼
Target URLs → status, latency, cert expiry
        │
        ▼
Application Insights → Log Analytics → KQL
```

Deployed by `main.bicep`: storage account, App Service plan (Y1), Function App with a system-assigned identity, Application Insights, and a Log Analytics workspace.

## Repo layout

```
azure-uptime-sentinel/
├── infrastructure/
│   ├── main.bicep
│   └── parameters.json
├── src/
│   ├── function_app.py
│   ├── host.json
│   └── requirements.txt
└── .github/workflows/
    └── deploy.yml
```

`deploy.yml` is only a placeholder for now. I deploy from my terminal.

## Deploy

You need the Azure CLI (with Bicep), Azure Functions Core Tools v4 and Python 3.11.

Create the resource group:

```powershell
az login
az group create --name rg-uptime-sentinel-lab --location northeurope
```

Deploy the infrastructure:

```powershell
az deployment group create `
    --resource-group rg-uptime-sentinel-lab `
    --template-file infrastructure/main.bicep `
    --parameters infrastructure/parameters.json `
    --output table
```

Publish the code. Run this from `src/`, because that's where `host.json` is:

```powershell
cd src
func azure functionapp publish uptimesentinel-func --python
cd ..
```

The first cold start takes a few minutes, and logs take a few more to show up in Application Insights.

## Changing the targets

Edit `infrastructure/parameters.json`:

```json
{
  "parameters": {
    "targetUrls": {
      "value": [
        "https://microsoft.com",
        "https://httpbin.org/status/200"
      ]
    }
  }
}
```

Bicep joins these into the `TARGET_URLS` app setting. You can also edit that setting directly on the Function App.

## Checking the results

In Application Insights, open Logs and run:

```kusto
traces
| where timestamp > ago(1h)
| where message has "CHECK_RESULT" or message has "CHECK_FAILURE" or message has "SSL_"
| project timestamp, message
| order by timestamp desc
```

Anything that isn't UP:

```kusto
traces
| where timestamp > ago(24h)
| where message has "CHECK_FAILURE" or message has "Status: DEGRADED"
| project timestamp, message
| order by timestamp desc
```

Example output:

```
CHECK_RESULT | URL: https://microsoft.com | Status: UP | Code: 200 | Latency: 101ms | SSL Days: 61
```

## Problems I hit

- **Deployment failed with `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING has an invalid value`.** My storage connection strings were empty placeholders. I now build them from the real storage account with `listKeys()`.
- **App settings weren't applying.** I had them under a `sites/config` resource named `web`, which is the wrong place. They now sit in `siteConfig.appSettings`.
- **Storage account name clashes.** Names are global, so I now use `uniqueString(resourceGroup().id)`.
- **SSL check failing silently.** The `cryptography` certificate attributes I used didn't exist, so every check returned no expiry data. I replaced it with the standard library (`ssl.getpeercert()` and `ssl.cert_time_to_seconds()`), which also removed a dependency.
- **Publish failed with "Unable to find project root".** I was running `func` from the repo root instead of `src/`.
- **Generated code needs checking.** Some of the original code came from an AI assistant and looked fine but didn't work. The logs showed what was actually happening, so I now verify in Application Insights before calling anything done.

## To do

- Azure Monitor alert rules for `DOWN` and `DEGRADED`
- Identity-based storage access instead of account keys
- A working GitHub Actions deployment using OIDC
- Unit tests for the status and expiry logic

## Cost

It runs on the Consumption plan, so you pay per execution plus storage and log ingestion. I haven't priced it exactly. Set a budget alert on the resource group.

## Cleanup

```powershell
az group delete --name rg-uptime-sentinel-lab --yes --no-wait
```
