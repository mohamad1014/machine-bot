param location string
@minLength(3)
param accountName string
param databaseName string
param containerName string

resource account 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    enableFreeTier: true
    publicNetworkAccess: 'Enabled'
    capabilities: []
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  name: databaseName
  parent: account
  properties: {
    resource: {
      id: databaseName
    }
    options: {
      throughput: 400
    }
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: containerName
  parent: database
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [ '/pk' ]
        kind: 'Hash'
      }
    }
    options: {
      throughput: 400
    }
  }
}

// Lease container for change feed processor
resource leaseContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: 'leases'
  parent: database
  properties: {
    resource: {
      id: 'leases'
      partitionKey: {
        paths: [ '/id' ]
        kind: 'Hash'
      }
    }
    options: {
      throughput: 400
    }
  }
}

output endpoint string = account.properties.documentEndpoint
output primaryKey string = listKeys(account.id, account.apiVersion).primaryMasterKey
output connectionString string = listConnectionStrings(account.id, account.apiVersion).connectionStrings[0].connectionString
