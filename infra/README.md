Infrastructure as Code (Bicep)

This folder contains Bicep templates to provision a Python 3.12 Azure Functions app (v4 runtime, Python v2 programming model) and common dependencies: Storage, Application Insights, Cosmos DB, and Azure SQL.

Prerequisites
- Azure CLI logged in: `az login`
- Bicep (bundled with Azure CLI)
- Resource group created or create one during deployment

Parameters (main.bicep)
- `location`: Azure region (e.g., `westeurope`)
- `namePrefix`: Prefix for resource names (lowercase, letters and digits)
- `cosmosDbName`: Cosmos DB database name
- `cosmosContainerName`: Cosmos DB container name
- `sqlAdminLogin` / `sqlAdminPassword`: SQL admin credentials
- `manualsMdConnectionString`: Connection string for manuals markdown storage (blob container)
- `azureOpenAiEndpoint`: Azure OpenAI endpoint URL
- `azureOpenAiApiKey`: Azure OpenAI API key
- `azureOpenAiDeployment`: Azure OpenAI deployment name

Deploy
1) Create resource group (if needed):
   az group create -n rg-machine-bot -l westeurope

2) Deploy:
   az deployment group create \
     -g rg-machine-bot \
     -f infra/main.bicep \
     -p namePrefix=mbot location=westeurope cosmosDbName=mbotdb cosmosContainerName=mbotitems \
        sqlAdminLogin=sqladmin sqlAdminPassword=YOUR_STRONG_PASSWORD \
        manualsMdConnectionString=YOUR_STORAGE_CONNECTION \
        azureOpenAiEndpoint=YOUR_OPENAI_ENDPOINT \
        azureOpenAiApiKey=YOUR_OPENAI_KEY \
        azureOpenAiDeployment=YOUR_OPENAI_DEPLOYMENT

Outputs include connection values and URLs you can set as application settings locally (or wire via Key Vault). The `conversationRunUrl`
output gives the HTTP endpoint for the sample function (requires a function key).

