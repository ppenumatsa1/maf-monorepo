targetScope = 'resourceGroup'

@description('Existing public Foundry account name.')
param foundryAccountName string

@description('Existing Foundry project name.')
param foundryProjectName string

@description('Existing Container Registry name.')
param containerRegistryName string

@description('PostgreSQL Flexible Server name.')
param postgresServerName string

@description('PostgreSQL Flexible Server location.')
param postgresServerLocation string

@secure()
@description('PostgreSQL administrator password, supplied only through the local azd environment.')
param postgresAdministratorPassword string

@description('PostgreSQL administrator login used when creating the server.')
param postgresAdministratorLogin string

@description('Public IPv4 address permitted to run release-time schema and credential setup.')
param postgresOperatorIp string

@description('Database used by the hosted underwriting runtime.')
param postgresDatabaseName string

@description('PostgreSQL major version captured from the server before rebuild.')
param postgresVersion string = '17'

@description('PostgreSQL compute SKU captured from the server before rebuild.')
param postgresSkuName string = 'Standard_D2ds_v5'

@description('PostgreSQL compute tier for the captured SKU.')
param postgresSkuTier string = 'GeneralPurpose'

@description('PostgreSQL storage size in GiB captured from the server before rebuild.')
param postgresStorageSizeGB int = 128

@description('PostgreSQL backup retention days captured from the server before rebuild.')
param postgresBackupRetentionDays int = 7

@description('PostgreSQL geo-redundant backup setting captured from the server before rebuild.')
@allowed([
  'Enabled'
  'Disabled'
])
param postgresGeoRedundantBackup string = 'Disabled'

@description('Existing Container Apps environment name.')
param containerAppsEnvironmentName string

@description('Existing backend Container App name.')
param backendContainerAppName string

@description('User-assigned identity attached to the public backend Container App.')
param publicBackendManagedIdentityName string

@description('Existing frontend Container App name.')
param frontendContainerAppName string

@description('Existing Application Insights component name.')
param applicationInsightsName string

@description('Existing Log Analytics workspace name linked to Application Insights.')
param logAnalyticsWorkspaceName string

@description('Dedicated storage account for Foundry evaluation artifacts.')
param evaluationStorageAccountName string = 'azstwhcedyxchnbtmeval'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

// This normal resource declaration creates or updates the server and preserves
// the captured creation configuration alongside the approved public posture.
resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: postgresServerName
  location: postgresServerLocation
  sku: {
    name: postgresSkuName
    tier: postgresSkuTier
  }
  properties: {
    administratorLogin: postgresAdministratorLogin
    administratorLoginPassword: postgresAdministratorPassword
    version: postgresVersion
    storage: {
      storageSizeGB: postgresStorageSizeGB
    }
    backup: {
      backupRetentionDays: postgresBackupRetentionDays
      geoRedundantBackup: postgresGeoRedundantBackup
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
      tenantId: subscription().tenantId
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

// This updates the pre-existing temporary rule in place rather than adding a
// second, broader exception.  0.0.0.0 is Azure services, not internet-wide.
resource postgresAzureServicesFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgresServer
  name: 'allow-all-temporary'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource postgresReleaseOperatorFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgresServer
  name: 'allow-release-operator'
  properties: {
    startIpAddress: postgresOperatorIp
    endIpAddress: postgresOperatorIp
  }
}

resource postgresRuntimeDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgresServer
  name: postgresDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppsEnvironmentName
}

resource backendContainerApp 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: backendContainerAppName
}

resource publicBackendManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: publicBackendManagedIdentityName
}

resource frontendContainerApp 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: frontendContainerAppName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource acrPullRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  scope: resourceGroup()
}

resource acrRepositoryReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: 'b93aa761-3e63-49ed-ac28-beffa264f7ac'
  scope: resourceGroup()
}

resource logAnalyticsReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '73c42c96-874c-492b-b04d-ab87d138a893'
  scope: resourceGroup()
}

resource cognitiveServicesOpenAIUserRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  scope: resourceGroup()
}

resource foundryUserRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  scope: resourceGroup()
}

// Foundry hosted agents need both current registry pull roles when the
// registry does not advertise a single ABAC-only pull surface.
resource foundryProjectAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, foundryProject.id, acrPullRole.id)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectAcrRepositoryReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, foundryProject.id, acrRepositoryReaderRole.id)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrRepositoryReaderRole.id
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectApplicationInsightsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(applicationInsights.id, foundryProject.id, logAnalyticsReaderRole.id)
  scope: applicationInsights
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectLogAnalyticsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalyticsWorkspace.id, foundryProject.id, logAnalyticsReaderRole.id)
  scope: logAnalyticsWorkspace
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// The project identity supports Foundry-managed model operations. The hosted
// runtime identity receives the same least-privilege data-plane role during
// agent deployment after that identity exists.
resource foundryProjectOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, foundryProject.id, cognitiveServicesOpenAIUserRole.id)
  scope: foundryAccount
  properties: {
    roleDefinitionId: cognitiveServicesOpenAIUserRole.id
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// The Responses protocol requires Foundry project data-plane actions in addition
// to the OpenAI data-plane permission already assigned on the account.
resource publicBackendFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryProject.id, publicBackendManagedIdentity.id, foundryUserRole.id)
  scope: foundryProject
  properties: {
    roleDefinitionId: foundryUserRole.id
    principalId: publicBackendManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectApplicationInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: foundryProject
  name: 'ApplicationInsights'
  properties: {
    category: 'AppInsights'
    target: applicationInsights.id
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: applicationInsights.properties.ConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsights.id
    }
  }
  dependsOn: [
    foundryProjectApplicationInsightsReader
    foundryProjectLogAnalyticsReader
  ]
}

resource evaluationStorageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: evaluationStorageAccountName
  location: resourceGroup().location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    // The enforced StorageAccount_PublicNetwork_Modify policy requires this
    // setting. Native evaluator generation needs a policy exemption or private
    // networking; the release uses trace evaluation instead.
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

resource storageBlobDataOwnerRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  scope: resourceGroup()
}

resource foundryAccountEvaluationStorageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(evaluationStorageAccount.id, foundryAccount.id, storageBlobDataOwnerRole.id)
  scope: evaluationStorageAccount
  properties: {
    roleDefinitionId: storageBlobDataOwnerRole.id
    principalId: foundryAccount.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectEvaluationStorageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(evaluationStorageAccount.id, foundryProject.id, storageBlobDataOwnerRole.id)
  scope: evaluationStorageAccount
  properties: {
    roleDefinitionId: storageBlobDataOwnerRole.id
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource evaluationStorageConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: foundryAccount
  name: 'evaluation-artifacts'
  properties: {
    category: 'AzureStorageAccount'
    target: evaluationStorageAccount.properties.primaryEndpoints.blob
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: evaluationStorageAccount.id
      location: evaluationStorageAccount.location
      purpose: 'foundry-evaluation-artifacts'
    }
  }
  dependsOn: [
    foundryAccountEvaluationStorageAccess
    foundryProjectEvaluationStorageAccess
  ]
}

// Foundry evaluator workers use this private runtime connection while
// evaluation-artifacts is shared with the project for result persistence.
resource runtimeStorageConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: foundryAccount
  name: 'runtime-storage'
  properties: {
    category: 'AzureStorageAccount'
    target: evaluationStorageAccount.properties.primaryEndpoints.blob
    authType: 'AAD'
    isSharedToAll: false
    metadata: {
      ApiType: 'Azure'
      ResourceId: evaluationStorageAccount.id
      location: evaluationStorageAccount.location
      purpose: 'foundry-runtime-artifacts'
    }
  }
  dependsOn: [
    foundryAccountEvaluationStorageAccess
    foundryProjectEvaluationStorageAccess
  ]
}

// azd requires at least one ARM resource. This nested deployment intentionally
// has no child resources and records only validation of the existing topology.
resource resourceReuseValidation 'Microsoft.Resources/deployments@2024-03-01' = {
  name: 'underwriting-foundry-reuse-validation'
  properties: {
    mode: 'Incremental'
    expressionEvaluationOptions: {
      scope: 'Inner'
    }
    template: {
      '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
      contentVersion: '1.0.0.0'
      resources: []
    }
  }
}

output AZURE_AI_PROJECT_ENDPOINT string = 'https://${foundryAccount.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
output AZURE_AI_PROJECT_ID string = foundryProject.id
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output APPLICATIONINSIGHTS_RESOURCE_ID string = applicationInsights.id
output AZURE_POSTGRES_SERVER_FQDN string = postgresServer.properties.fullyQualifiedDomainName
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = containerAppsEnvironment.id
output BACKEND_CONTAINER_APP_ID string = backendContainerApp.id
output FRONTEND_CONTAINER_APP_ID string = frontendContainerApp.id
