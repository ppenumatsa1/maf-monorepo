targetScope = 'resourceGroup'

@description('Deployment location')
param location string

@description('AZD environment name used for deployment and evidence correlation')
param azdEnvironmentName string

@description('Prefix used with the deployment scope for deterministic naming')
@minLength(3)
param namePrefix string

@description('Network profile for the Foundry-hosted infrastructure')
@allowed([
  'private'
])
param networkMode string

@description('Bootstrap creates stateful resources and initial workloads; reuse references them without resetting workload images or secrets.')
@allowed([
  'bootstrap'
  'reuse'
])
param deploymentMode string

@description('Foundry project name')
param foundryProjectName string

@description('Hosted agent name used to compose default responses URL')
param hostedAgentName string

@description('Restore a soft-deleted Foundry account with this name when Azure reports one. Keep true for the intentional private-lane teardown; set false only after purging the account name.')
param restoreFoundryAccount bool

@description('Cosmos DB region')
param cosmosLocation string

@description('AI Search region')
@minLength(1)
param aiSearchLocation string

@description('AI Search SKU name')
param aiSearchSkuName string

@description('Name of the callback token setting used by backend event ingress')
param foundryEventCallbackTokenSettingName string = 'FOUNDRY_EVENT_CALLBACK_TOKEN'

@description('VNet address prefix')
param vnetAddressPrefix string

@description('Agent subnet name')
param agentSubnetName string = 'snet-agent-host'

@description('Agent subnet prefix')
param agentSubnetPrefix string

@description('Private endpoint subnet name')
param privateEndpointSubnetName string = 'snet-private-endpoints'

@description('Private endpoint subnet prefix')
param privateEndpointSubnetPrefix string

@description('Azure Container Apps infrastructure subnet name')
param containerAppsSubnetName string = 'snet-container-apps'

@description('Azure Container Apps infrastructure subnet prefix. Consumption environments require at least /23.')
param containerAppsSubnetPrefix string

@description('Enable the public frontend and internal backend Container Apps.')
param enableContainerApps bool

@description('Backend bootstrap or azd-published container image')
param backendImageName string

@description('Frontend bootstrap or azd-published container image')
param frontendImageName string

@description('Create NAT gateway for controlled outbound from the agent subnet.')
param createNatGateway bool

@description('Enable private runner access resources (runner subnet, Bastion, and VM).')
param createPrivateRunnerAccess bool

@description('Assign resource-group RBAC to runner UAMI so azd can validate and run deployments non-interactively.')
param assignRunnerResourceGroupRbac bool

@description('Also assign User Access Administrator for runner UAMI when templates create role assignments.')
param assignRunnerUserAccessAdministrator bool = false

@description('Runner subnet name')
param runnerSubnetName string = 'snet-runner'

@description('Runner subnet prefix')
param runnerSubnetPrefix string

@description('Azure Bastion subnet name. Must be AzureBastionSubnet.')
param bastionSubnetName string = 'AzureBastionSubnet'

@description('Azure Bastion subnet prefix (minimum /26).')
param bastionSubnetPrefix string

@description('Create Azure Bastion host for browser/SSH tunneling access.')
param createBastionHost bool

@description('Create a private VM runner in the runner subnet.')
param createRunnerVm bool

@description('Runner VM size')
param runnerVmSize string

@description('Runner VM admin username')
param runnerVmAdminUsername string

@description('SSH public key for runner VM admin user. Required when createRunnerVm is true.')
@secure()
@minLength(1)
param runnerVmSshPublicKey string

@description('Private DNS zones used for private endpoint resolution')
param privateDnsZoneNames array = [
  'privatelink.blob.core.windows.net'
  'privatelink.search.windows.net'
  'privatelink.documents.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.azurecr.io'
  'privatelink.postgres.database.azure.com'
]

@description('Create private DNS VNet links.')
param createPrivateDnsVnetLinks bool

@description('Create private endpoints for dependent services.')
param createPrivateEndpoints bool

@description('Assign pre-capability-host RBAC (Storage Blob Data Contributor, Cosmos DB Operator, Search roles).')
param assignPreCaphostRbac bool

@description('Assign post-capability-host RBAC (Storage Blob Data Owner conditional and Cosmos SQL role).')
param assignPostCaphostRbac bool

@description('Create or update account-level capability host configuration.')
param createAccountCapabilityHost bool

@description('Create or update project-level capability host configuration.')
param createProjectCapabilityHost bool

@description('Manage project connections through the connections API. Disable on reruns when capability host already owns these connections.')
param manageProjectConnections bool

@description('Enable Standard Agent network injection scenario on newly created Foundry account.')
param enableStandardAgentNetworkInjection bool

@description('Foundry chat deployment name')
param foundryChatDeploymentName string

@description('Foundry chat model format')
param foundryChatModelFormat string

@description('Foundry chat model name')
param foundryChatModelName string

@description('Foundry chat model version')
param foundryChatModelVersion string

@description('Foundry chat deployment SKU name')
param foundryChatDeploymentSkuName string

@description('Foundry chat deployment capacity')
param foundryChatDeploymentCapacity int

@description('Foundry embeddings deployment name')
param foundryEmbeddingsDeploymentName string

@description('Foundry embeddings model format')
param foundryEmbeddingsModelFormat string

@description('Foundry embeddings model name')
param foundryEmbeddingsModelName string

@description('Foundry embeddings model version')
param foundryEmbeddingsModelVersion string

@description('Foundry embeddings deployment SKU name')
param foundryEmbeddingsDeploymentSkuName string

@description('Foundry embeddings deployment capacity')
param foundryEmbeddingsDeploymentCapacity int

@description('Responsible AI policy name applied to model deployments')
param foundryRaiPolicyName string

@description('Hosted runtime PostgreSQL connection string stored in Foundry CustomKeys connection as database_url')
@secure()
param runtimeDatabaseUrl string = ''

@description('Create PostgreSQL Flexible Server for workflow persistence. Set false when connecting the private endpoint to an existing canonical server.')
param createPostgresServer bool

@description('PostgreSQL administrator username.')
param postgresAdminUsername string

@description('PostgreSQL administrator password (required when createPostgresServer is true).')
@secure()
@minLength(1)
param postgresAdminPassword string

@description('Workflow database name.')
param postgresDatabaseName string

@description('PostgreSQL server location.')
param postgresLocation string

@description('PostgreSQL Flexible Server SKU name')
param postgresSkuName string

@description('PostgreSQL Flexible Server SKU tier')
param postgresSkuTier string

@description('PostgreSQL major version')
param postgresVersion string

@description('PostgreSQL storage size in GB')
param postgresStorageSizeGb int

@description('PostgreSQL backup retention in days')
param postgresBackupRetentionDays int

@description('Enable the PostgreSQL private endpoint and DNS zone.')
param enablePostgresPrivateEndpoint bool

var suffix = toLower(uniqueString(resourceGroup().id))
var normalizedPrefix = toLower(replace(namePrefix, '-', ''))
var effectiveFoundryAccountName = take('${normalizedPrefix}ai${suffix}', 64)
var effectiveStorageAccountName = take('${normalizedPrefix}st${suffix}', 24)
var effectiveCosmosAccountName = take('${normalizedPrefix}cosmos${suffix}', 44)
var effectiveAiSearchName = take('${normalizedPrefix}srch${suffix}', 60)
var effectiveAiSearchLocation = aiSearchLocation
var effectiveContainerRegistryName = take('${normalizedPrefix}acr${suffix}', 50)
var effectiveVirtualNetworkName = '${normalizedPrefix}-vnet-${suffix}'
var effectiveNatGatewayName = take('${namePrefix}-nat-${suffix}', 80)
var effectiveNatPublicIpName = take('${namePrefix}-nat-pip-${suffix}', 80)
var containerAppsEnvironmentName = take('${namePrefix}-aca-${suffix}', 60)
var backendContainerAppName = take('${namePrefix}-backend-${suffix}', 32)
var frontendContainerAppName = take('${namePrefix}-frontend-${suffix}', 32)
var runnerVmName = take('${namePrefix}-runner-${suffix}', 64)
var runnerSubnetNsgName = take('${namePrefix}-runner-nsg-${suffix}', 80)
var runnerUamiName = take('${namePrefix}-runner-id-${suffix}', 128)
var bastionHostName = take('${namePrefix}-bastion-${suffix}', 80)
var bastionPublicIpName = take('${namePrefix}-bastion-pip-${suffix}', 80)
var accountCapabilityHostName = 'aml_aiagentservice'
var projectCapabilityHostName = take('${normalizedPrefix}projhost${suffix}', 64)
var effectiveCosmosConnectionName = '${effectiveCosmosAccountName}-${foundryProjectName}'
var effectiveStorageConnectionName = '${effectiveStorageAccountName}-${foundryProjectName}'
var effectiveAiSearchConnectionName = '${effectiveAiSearchName}-${foundryProjectName}'
var effectiveRuntimeConnectionName = take('${normalizedPrefix}runtime${suffix}', 64)
var effectivePostgresServerName = take('${normalizedPrefix}pg${suffix}', 63)
var effectivePrivateDnsZoneNames = union(privateDnsZoneNames, [
  'privatelink.postgres.database.azure.com'
])
var effectiveCosmosLocation = cosmosLocation
var privateNetworking = networkMode == 'private'
var bootstrapDeployment = deploymentMode == 'bootstrap'
var createPostgresServerEffective = bootstrapDeployment && createPostgresServer
var enableNat = privateNetworking && createNatGateway
var enablePrivateDns = privateNetworking
var enablePrivateEndpoints = privateNetworking && createPrivateEndpoints
var enableAgentNetworkInjection = privateNetworking && enableStandardAgentNetworkInjection
var enablePrivateRunnerAccess = privateNetworking && createPrivateRunnerAccess
var enablePrivateContainerApps = privateNetworking && enableContainerApps && bootstrapDeployment
var agentSubnetResourceId = resourceId('Microsoft.Network/virtualNetworks/subnets', effectiveVirtualNetworkName, agentSubnetName)
var foundryNetworkInjectionProperties = enableAgentNetworkInjection ? {
  #disable-next-line BCP037
  networkInjections: [
    {
      #disable-next-line BCP037
      scenario: 'agent'
      #disable-next-line BCP037
      subnetArmId: agentSubnetResourceId
      #disable-next-line BCP037
      useMicrosoftManagedNetwork: false
    }
  ]
} : {}

#disable-next-line no-hardcoded-env-urls
var blobZoneName = 'privatelink.blob.core.windows.net'
#disable-next-line no-hardcoded-env-urls
var searchZoneName = 'privatelink.search.windows.net'
#disable-next-line no-hardcoded-env-urls
var cosmosZoneName = 'privatelink.documents.azure.com'
#disable-next-line no-hardcoded-env-urls
var foundryServicesZoneName = 'privatelink.services.ai.azure.com'
#disable-next-line no-hardcoded-env-urls
var foundryCognitiveZoneName = 'privatelink.cognitiveservices.azure.com'
#disable-next-line no-hardcoded-env-urls
var foundryOpenAiZoneName = 'privatelink.openai.azure.com'

var blobZoneIndex = indexOf(privateDnsZoneNames, blobZoneName)
var searchZoneIndex = indexOf(privateDnsZoneNames, searchZoneName)
var cosmosZoneIndex = indexOf(privateDnsZoneNames, cosmosZoneName)
var foundryServicesZoneIndex = indexOf(privateDnsZoneNames, foundryServicesZoneName)
var foundryCognitiveZoneIndex = indexOf(privateDnsZoneNames, foundryCognitiveZoneName)
var foundryOpenAiZoneIndex = indexOf(privateDnsZoneNames, foundryOpenAiZoneName)
var acrZoneIndex = indexOf(privateDnsZoneNames, 'privatelink.azurecr.io')
var postgresZoneIndex = indexOf(effectivePrivateDnsZoneNames, 'privatelink.postgres.database.azure.com')
var resolvedProjectPrincipalId = foundryProject.identity.principalId
var resolvedProjectWorkspaceId = manageProjectConnections ? projectConnections!.outputs.projectWorkspaceId : ''
var resolvedCosmosConnectionName = manageProjectConnections ? projectConnections!.outputs.cosmosConnection : effectiveCosmosConnectionName
var resolvedStorageConnectionName = manageProjectConnections ? projectConnections!.outputs.storageConnection : effectiveStorageConnectionName
var resolvedAiSearchConnectionName = manageProjectConnections ? projectConnections!.outputs.aiSearchConnection : effectiveAiSearchConnectionName
var resolvedApplicationInsightsConnectionName = manageProjectConnections ? projectConnections!.outputs.applicationInsightsConnection : 'ApplicationInsights'
var resolvedApplicationInsightsConnectionId = manageProjectConnections ? projectConnections!.outputs.applicationInsightsConnectionId : resourceId('Microsoft.CognitiveServices/accounts/projects/connections', effectiveFoundryAccountName, foundryProjectName, 'ApplicationInsights')
var resolvedRuntimeConnectionName = manageProjectConnections && !empty(runtimeDatabaseUrl) ? runtimeConnection!.outputs.runtimeConnection : effectiveRuntimeConnectionName

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-08-01-preview' = {
  name: effectiveContainerRegistryName
  location: location
  sku: {
    name: 'Premium'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'
    policies: {
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
    }
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: take('${namePrefix}-mon-${suffix}-law', 63)
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: take('${namePrefix}-mon-${suffix}-appi', 260)
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: effectiveStorageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    // The private deployment uses the blob private endpoint; do not reopen an
    // existing private Storage account for Azure-service traffic.
    publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'
    networkAcls: privateNetworking ? {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    } : {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = if (createPostgresServerEffective) {
  name: effectivePostgresServerName
  location: postgresLocation
  sku: {
    name: postgresSkuName
    tier: postgresSkuTier
  }
  properties: {
    administratorLogin: postgresAdminUsername
    administratorLoginPassword: postgresAdminPassword
    version: postgresVersion
    storage: {
      storageSizeGB: postgresStorageSizeGb
    }
    backup: {
      backupRetentionDays: postgresBackupRetentionDays
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Disabled'
    }
  }
}

resource existingPostgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = if (!createPostgresServerEffective) {
  name: effectivePostgresServerName
}

resource postgresWorkflowDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = if (createPostgresServerEffective) {
  name: postgresDatabaseName
  parent: postgresServer
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource aiSearch 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: effectiveAiSearchName
  location: effectiveAiSearchLocation
  sku: {
    name: aiSearchSkuName
  }
  properties: {
    publicNetworkAccess: privateNetworking ? 'disabled' : 'enabled'
  }
}

resource cosmosDB 'Microsoft.DocumentDB/databaseAccounts@2024-12-01-preview' = {
  name: effectiveCosmosAccountName
  location: effectiveCosmosLocation
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: effectiveCosmosLocation
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'
    enableAutomaticFailover: true
    disableLocalAuth: true
  }
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: effectiveFoundryAccountName
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: union({
    allowProjectManagement: true
    customSubDomainName: effectiveFoundryAccountName
    disableLocalAuth: true
    networkAcls: privateNetworking ? {
      defaultAction: 'Deny'
      virtualNetworkRules: []
      ipRules: []
      bypass: 'AzureServices'
    } : {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'
    ...foundryNetworkInjectionProperties
  }, restoreFoundryAccount ? {
    restore: true
  } : {})
  dependsOn: privateNetworking ? [
    virtualNetwork
  ] : []
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundryAccount
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: foundryProjectName
    description: 'MAF order resolution Foundry-hosted project'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundryAccount
  name: foundryChatDeploymentName
  sku: {
    name: foundryChatDeploymentSkuName
    capacity: foundryChatDeploymentCapacity
  }
  properties: {
    model: {
      format: foundryChatModelFormat
      name: foundryChatModelName
      version: foundryChatModelVersion
    }
    raiPolicyName: foundryRaiPolicyName
  }
}

resource embeddingsDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundryAccount
  name: foundryEmbeddingsDeploymentName
  sku: {
    name: foundryEmbeddingsDeploymentSkuName
    capacity: foundryEmbeddingsDeploymentCapacity
  }
  properties: {
    model: {
      format: foundryEmbeddingsModelFormat
      name: foundryEmbeddingsModelName
      version: foundryEmbeddingsModelVersion
    }
    raiPolicyName: foundryRaiPolicyName
  }
  dependsOn: [
    chatDeployment
  ]
}

resource projectFoundryUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, foundryProject.id, 'project-foundry-user')
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, foundryProject.id, 'project-acr-pull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectAcrRepositoryReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, foundryProject.id, 'project-acr-repository-reader')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b93aa761-3e63-49ed-ac28-beffa264f7ac')
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

var logAnalyticsReaderRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '73c42c96-874c-492b-b04d-ab87d138a893'
)

var monitoringMetricsPublisherRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '3913510d-42f4-4e42-8a64-420c390055eb'
)

resource projectTraceReaderApplicationInsightsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(applicationInsights.id, foundryProject.id, logAnalyticsReaderRoleDefinitionId)
  scope: applicationInsights
  properties: {
    roleDefinitionId: logAnalyticsReaderRoleDefinitionId
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectTelemetryPublisherApplicationInsightsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(applicationInsights.id, foundryProject.id, monitoringMetricsPublisherRoleDefinitionId)
  scope: applicationInsights
  properties: {
    roleDefinitionId: monitoringMetricsPublisherRoleDefinitionId
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectTraceReaderLogAnalyticsRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalytics.id, foundryProject.id, logAnalyticsReaderRoleDefinitionId)
  scope: logAnalytics
  properties: {
    roleDefinitionId: logAnalyticsReaderRoleDefinitionId
    principalId: foundryProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource natPublicIp 'Microsoft.Network/publicIPAddresses@2023-09-01' = if (enableNat) {
  name: effectiveNatPublicIpName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource natGateway 'Microsoft.Network/natGateways@2023-09-01' = if (enableNat) {
  name: effectiveNatGatewayName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    idleTimeoutInMinutes: 10
    publicIpAddresses: [
      {
        id: natPublicIp.id
      }
    ]
  }
}

module virtualNetwork './modules/vnet.bicep' = if (privateNetworking) {
  name: 'foundry-vnet-${suffix}'
  params: {
    enabled: privateNetworking
    location: location
    vnetName: effectiveVirtualNetworkName
    vnetAddressPrefix: vnetAddressPrefix
    agentSubnetName: agentSubnetName
    agentSubnetPrefix: agentSubnetPrefix
    natGatewayResourceId: enableNat ? natGateway.id : ''
    privateEndpointSubnetName: privateEndpointSubnetName
    privateEndpointSubnetPrefix: privateEndpointSubnetPrefix
    // Keep this subnet declared even when apps are disabled on a rerun, so the
    // VNet deployment cannot prune an environment's infrastructure subnet.
    createContainerAppsSubnet: true
    containerAppsSubnetName: containerAppsSubnetName
    containerAppsSubnetPrefix: containerAppsSubnetPrefix
    // Keep runner subnet declared in VNet to avoid destructive subnet pruning on shared reruns.
    createRunnerSubnet: true
    runnerSubnetName: runnerSubnetName
    runnerSubnetPrefix: runnerSubnetPrefix
    runnerSubnetNsgResourceId: ''
    runnerSubnetNatGatewayResourceId: enableNat ? natGateway.id : ''
    // Keep AzureBastionSubnet declared in VNet to avoid deletion attempts when Bastion already exists.
    createBastionSubnet: true
    bastionSubnetName: bastionSubnetName
    bastionSubnetPrefix: bastionSubnetPrefix
  }
}

module privateRunnerAccess './modules/private-runner-access.bicep' = if (enablePrivateRunnerAccess) {
  name: 'private-runner-access-${suffix}'
  params: {
    enabled: enablePrivateRunnerAccess
    location: location
    vnetName: effectiveVirtualNetworkName
    runnerSubnetName: runnerSubnetName
    runnerSubnetPrefix: runnerSubnetPrefix
    createRunnerSubnet: false
    bastionSubnetName: bastionSubnetName
    bastionSubnetPrefix: bastionSubnetPrefix
    createBastionSubnet: false
    runnerNsgName: runnerSubnetNsgName
    runnerUamiName: runnerUamiName
    createRunnerUami: true
    createBastion: createBastionHost
    createRunnerVm: createRunnerVm
    runnerVmName: runnerVmName
    runnerVmSize: runnerVmSize
    runnerAdminUsername: runnerVmAdminUsername
    runnerSshPublicKey: runnerVmSshPublicKey
    bastionName: bastionHostName
    bastionPublicIpName: bastionPublicIpName
  }
  dependsOn: [
    virtualNetwork
  ]
}

module runnerResourceGroupRbac './modules/runner-resource-group-rbac.bicep' = if (enablePrivateRunnerAccess && createRunnerVm && assignRunnerResourceGroupRbac) {
  name: 'runner-resource-group-rbac-${suffix}'
  params: {
    principalId: privateRunnerAccess!.outputs.runnerUamiPrincipalId
    assignContributor: true
    assignUserAccessAdministrator: assignRunnerUserAccessAdministrator
  }
  dependsOn: [
    privateRunnerAccess
  ]
}

module privateDns './modules/private-dns.bicep' = if (enablePrivateDns) {
  name: 'private-network-dns'
  params: {
    enabled: true
    virtualNetworkId: virtualNetwork!.outputs.id
    zoneNames: effectivePrivateDnsZoneNames
    createVnetLinks: createPrivateDnsVnetLinks
  }
}

module storagePrivateEndpoint './modules/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'private-endpoint-storage'
  params: {
    enabled: true
    location: location
    name: '${namePrefix}-storage-pe-${suffix}'
    subnetId: virtualNetwork!.outputs.privateEndpointSubnetId
    targetResourceId: storage.id
    groupIds: [
      'blob'
    ]
    privateDnsZoneIds: [
      privateDns!.outputs.zoneIds[blobZoneIndex]
    ]
  }
}

module searchPrivateEndpoint './modules/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'private-endpoint-search'
  params: {
    enabled: true
    location: location
    name: '${namePrefix}-search-pe-${suffix}'
    subnetId: virtualNetwork!.outputs.privateEndpointSubnetId
    targetResourceId: aiSearch.id
    groupIds: [
      'searchService'
    ]
    privateDnsZoneIds: [
      privateDns!.outputs.zoneIds[searchZoneIndex]
    ]
  }
}

module cosmosPrivateEndpoint './modules/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'private-endpoint-cosmos'
  params: {
    enabled: true
    location: location
    name: '${namePrefix}-cosmos-pe-${suffix}'
    subnetId: virtualNetwork!.outputs.privateEndpointSubnetId
    targetResourceId: cosmosDB.id
    groupIds: [
      'Sql'
    ]
    privateDnsZoneIds: [
      privateDns!.outputs.zoneIds[cosmosZoneIndex]
    ]
  }
}

module foundryPrivateEndpoint './modules/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'private-endpoint-foundry-account'
  params: {
    enabled: true
    location: location
    name: '${namePrefix}-foundry-pe-${suffix}'
    subnetId: virtualNetwork!.outputs.privateEndpointSubnetId
    targetResourceId: foundryAccount.id
    groupIds: [
      'account'
    ]
    privateDnsZoneIds: [
      privateDns!.outputs.zoneIds[foundryServicesZoneIndex]
      privateDns!.outputs.zoneIds[foundryCognitiveZoneIndex]
      privateDns!.outputs.zoneIds[foundryOpenAiZoneIndex]
    ]
  }
}

module acrPrivateEndpoint './modules/private-endpoint.bicep' = if (enablePrivateEndpoints) {
  name: 'private-endpoint-acr'
  params: {
    enabled: true
    location: location
    name: '${namePrefix}-acr-pe-${suffix}'
    subnetId: virtualNetwork!.outputs.privateEndpointSubnetId
    targetResourceId: containerRegistry.id
    groupIds: [
      'registry'
    ]
    privateDnsZoneIds: [
      privateDns!.outputs.zoneIds[acrZoneIndex]
    ]
  }
}

module postgresPrivateEndpoint './modules/private-endpoint.bicep' = if (enablePrivateEndpoints && enablePostgresPrivateEndpoint) {
  name: 'private-endpoint-postgres'
  params: {
    enabled: true
    location: location
    name: '${namePrefix}-postgres-pe-${suffix}'
    subnetId: virtualNetwork!.outputs.privateEndpointSubnetId
    targetResourceId: createPostgresServerEffective ? postgresServer!.id : existingPostgresServer!.id
    groupIds: [
      'postgresqlServer'
    ]
    privateDnsZoneIds: [
      privateDns!.outputs.zoneIds[postgresZoneIndex]
    ]
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = if (enablePrivateContainerApps) {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: virtualNetwork!.outputs.containerAppsSubnetId
      internal: false
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
  dependsOn: [
    virtualNetwork
  ]
}

resource existingContainerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = if (privateNetworking && enableContainerApps && !bootstrapDeployment) {
  name: containerAppsEnvironmentName
}

resource containerAppsRegistryPullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (enablePrivateContainerApps) {
  name: '${containerAppsEnvironmentName}-acr-pull'
  location: location
}

resource containerAppsRegistryPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enablePrivateContainerApps) {
  name: guid(containerRegistry.id, containerAppsRegistryPullIdentity!.id, 'acr-pull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: containerAppsRegistryPullIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource backendContainerApp 'Microsoft.App/containerApps@2024-03-01' = if (enablePrivateContainerApps) {
  name: backendContainerAppName
  location: location
  tags: {
    'azd-service-name': 'backend'
  }
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${containerAppsRegistryPullIdentity!.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment!.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: containerAppsRegistryPullIdentity!.id
        }
      ]
      secrets: concat([
        {
          name: 'application-insights-connection-string'
          value: applicationInsights.properties.ConnectionString
        }
      ], empty(runtimeDatabaseUrl) ? [] : [
        {
          name: 'database-url'
          value: runtimeDatabaseUrl
        }
      ])
      ingress: {
        external: false
        allowInsecure: false
        targetPort: 8000
        transport: 'http'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImageName
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat([
            {
              name: 'APP_ENV'
              value: 'aca-private'
            }
            {
              name: 'STORE_PROVIDER'
              value: 'postgres'
            }
            {
              name: 'RUNTIME_TARGET'
              value: 'responses_wrapper'
            }
            {
              name: 'FOUNDRY_RESPONSES_ENDPOINT'
              value: foundryHostedResponsesUrl
            }
            {
              name: 'FOUNDRY_RESPONSES_TIMEOUT_SECONDS'
              value: '120'
            }
            {
              name: 'FOUNDRY_PROJECTS_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'FOUNDRY_MODEL_DEPLOYMENT_NAME'
              value: foundryChatDeploymentName
            }
            {
              name: 'ENABLE_TELEMETRY'
              value: 'true'
            }
            {
              name: 'ENABLE_INSTRUMENTATION'
              value: 'true'
            }
            {
              name: 'OTEL_SERVICE_NAME'
              value: 'maf-order-resolution-private-aca-backend'
            }
            {
              name: 'OTEL_SERVICE_NAMESPACE'
              value: 'maf-order-resolution'
            }
            {
              name: 'OTEL_RECORD_CONTENT'
              value: 'false'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'application-insights-connection-string'
            }
            {
              name: 'APPINSIGHTS_CONNECTION_STRING'
              secretRef: 'application-insights-connection-string'
            }
          ], empty(runtimeDatabaseUrl) ? [] : [
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'DB_SCHEMA_MANAGED_EXTERNALLY'
              value: 'true'
            }
          ])
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 24
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 15
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 6
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
  dependsOn: [
    containerAppsRegistryPullRoleAssignment
    postgresPrivateEndpoint
  ]
}

resource existingBackendContainerApp 'Microsoft.App/containerApps@2024-03-01' existing = if (privateNetworking && enableContainerApps && !bootstrapDeployment) {
  name: backendContainerAppName
}

resource backendContainerAppFoundryUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enablePrivateContainerApps) {
  name: guid(foundryAccount.id, backendContainerApp!.id, 'backend-foundry-user')
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: backendContainerApp!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource frontendContainerApp 'Microsoft.App/containerApps@2024-03-01' = if (enablePrivateContainerApps) {
  name: frontendContainerAppName
  location: location
  tags: {
    'azd-service-name': 'frontend'
  }
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${containerAppsRegistryPullIdentity!.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment!.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: containerAppsRegistryPullIdentity!.id
        }
      ]
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 5173
        transport: 'http'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: frontendImageName
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'NGINX_API_UPSTREAM'
              value: 'https://${backendContainerApp!.properties.configuration.ingress.fqdn}'
            }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 5173
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 24
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 5173
              }
              initialDelaySeconds: 15
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 5173
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 6
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
  dependsOn: [
    backendContainerApp
  ]
}

resource existingFrontendContainerApp 'Microsoft.App/containerApps@2024-03-01' existing = if (privateNetworking && enableContainerApps && !bootstrapDeployment) {
  name: frontendContainerAppName
}

module projectConnections './modules/foundry-project-existing-connections.bicep' = if (manageProjectConnections) {
  name: 'project-connections-${suffix}'
  params: {
    accountName: effectiveFoundryAccountName
    projectName: foundryProjectName
    location: location
    aiSearchName: effectiveAiSearchName
    aiSearchSubscriptionId: subscription().subscriptionId
    aiSearchResourceGroupName: resourceGroup().name
    storageAccountName: effectiveStorageAccountName
    storageSubscriptionId: subscription().subscriptionId
    storageResourceGroupName: resourceGroup().name
    cosmosAccountName: effectiveCosmosAccountName
    cosmosSubscriptionId: subscription().subscriptionId
    cosmosResourceGroupName: resourceGroup().name
    cosmosConnectionName: effectiveCosmosConnectionName
    storageConnectionName: effectiveStorageConnectionName
    aiSearchConnectionName: effectiveAiSearchConnectionName
    applicationInsightsResourceId: applicationInsights.id
    applicationInsightsConnectionString: applicationInsights.properties.ConnectionString
  }
  dependsOn: [
    foundryProject
    aiSearch
    storage
    cosmosDB
    storageAccountRoleAssignment
    storageAccountRoleAssignmentFoundryAccountIdentity
    cosmosAccountRoleAssignments
    aiSearchRoleAssignments
  ]
}

module runtimeConnection './modules/foundry-project-runtime-secret-connection.bicep' = if (manageProjectConnections && !empty(runtimeDatabaseUrl)) {
  name: 'runtime-secret-connection-${suffix}'
  params: {
    accountName: effectiveFoundryAccountName
    projectName: foundryProjectName
    location: location
    runtimeConnectionName: effectiveRuntimeConnectionName
    runtimeDatabaseUrl: runtimeDatabaseUrl
  }
  dependsOn: [
    projectConnections
  ]
}

module formatProjectWorkspaceId './modules/format-project-workspace-id.bicep' = if (manageProjectConnections) {
  name: 'format-workspace-id-${suffix}'
  params: {
    projectWorkspaceId: resolvedProjectWorkspaceId
  }
}

module storageAccountRoleAssignment './modules/azure-storage-account-role-assignment.bicep' = if (assignPreCaphostRbac) {
  name: 'storage-account-rbac-${suffix}'
  params: {
    storageAccountName: effectiveStorageAccountName
    projectPrincipalId: resolvedProjectPrincipalId
  }
  dependsOn: enablePrivateEndpoints ? [
    storagePrivateEndpoint
  ] : []
}

module storageAccountRoleAssignmentFoundryAccountIdentity './modules/azure-storage-account-role-assignment.bicep' = if (assignPreCaphostRbac) {
  name: 'storage-account-rbac-foundry-account-${suffix}'
  params: {
    storageAccountName: effectiveStorageAccountName
    projectPrincipalId: foundryAccount.identity.principalId
  }
  dependsOn: enablePrivateEndpoints ? [
    storagePrivateEndpoint
  ] : []
}

module cosmosAccountRoleAssignments './modules/cosmosdb-account-role-assignment.bicep' = if (assignPreCaphostRbac) {
  name: 'cosmos-account-rbac-${suffix}'
  params: {
    cosmosDBName: effectiveCosmosAccountName
    projectPrincipalId: resolvedProjectPrincipalId
  }
  dependsOn: enablePrivateEndpoints ? [
    cosmosPrivateEndpoint
  ] : []
}

module aiSearchRoleAssignments './modules/ai-search-role-assignments.bicep' = if (assignPreCaphostRbac) {
  name: 'search-account-rbac-${suffix}'
  params: {
    aiSearchName: effectiveAiSearchName
    projectPrincipalId: resolvedProjectPrincipalId
  }
  dependsOn: enablePrivateEndpoints ? [
    searchPrivateEndpoint
  ] : []
}

module addAccountCapabilityHost './modules/add-account-capability-host.bicep' = if (createAccountCapabilityHost) {
  name: 'account-capability-host-${suffix}'
  params: {
    accountName: effectiveFoundryAccountName
    accountCapabilityHostName: accountCapabilityHostName
    agentSubnetResourceId: privateNetworking ? virtualNetwork!.outputs.agentSubnetId : ''
  }
  dependsOn: enablePrivateEndpoints ? [
    foundryPrivateEndpoint
  ] : []
}

module addProjectCapabilityHost './modules/add-project-capability-host.bicep' = if (createProjectCapabilityHost && manageProjectConnections) {
  name: 'project-capability-host-${suffix}'
  params: {
    accountName: effectiveFoundryAccountName
    projectName: foundryProjectName
    projectCapabilityHostName: projectCapabilityHostName
    cosmosConnectionName: resolvedCosmosConnectionName
    storageConnectionName: resolvedStorageConnectionName
    aiSearchConnectionName: resolvedAiSearchConnectionName
  }
  dependsOn: [
    addAccountCapabilityHost
    storageAccountRoleAssignment
    storageAccountRoleAssignmentFoundryAccountIdentity
    cosmosAccountRoleAssignments
    aiSearchRoleAssignments
  ]
}

module storageContainersRoleAssignment './modules/blob-storage-container-role-assignments.bicep' = if (assignPostCaphostRbac && createProjectCapabilityHost && manageProjectConnections) {
  name: 'storage-container-rbac-${suffix}'
  params: {
    aiProjectPrincipalId: resolvedProjectPrincipalId
    storageName: effectiveStorageAccountName
    workspaceId: formatProjectWorkspaceId!.outputs.projectWorkspaceIdGuid
  }
  dependsOn: [
    addProjectCapabilityHost
  ]
}

module cosmosContainerRoleAssignments './modules/cosmos-container-role-assignments.bicep' = if (assignPostCaphostRbac && createProjectCapabilityHost && manageProjectConnections) {
  name: 'cosmos-container-rbac-${suffix}'
  params: {
    cosmosAccountName: effectiveCosmosAccountName
    projectWorkspaceId: formatProjectWorkspaceId!.outputs.projectWorkspaceIdGuid
    projectPrincipalId: resolvedProjectPrincipalId
  }
  dependsOn: [
    addProjectCapabilityHost
    storageContainersRoleAssignment
  ]
}

var resolvedPostgresServerName = createPostgresServerEffective ? postgresServer!.name : existingPostgresServer!.name
var postgresFullyQualifiedDomainName = createPostgresServerEffective ? postgresServer!.properties.fullyQualifiedDomainName : existingPostgresServer!.properties.fullyQualifiedDomainName
var foundryProjectEndpoint = 'https://${foundryAccount.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
var foundryHostedResponsesUrl = '${foundryProjectEndpoint}/agents/${hostedAgentName}/endpoint/protocols/openai/responses?api-version=v1'
var isCrossRegionAiSearch = toLower(effectiveAiSearchLocation) != toLower(location)
var resolvedFrontendFqdn = enableContainerApps ? (bootstrapDeployment ? frontendContainerApp!.properties.configuration.ingress.fqdn : existingFrontendContainerApp!.properties.configuration.ingress.fqdn) : ''

output foundryAccountName string = foundryAccount.name
output foundryAccountId string = foundryAccount.id
output foundryAccountEndpoints object = foundryAccount.properties.endpoints
output foundryProjectName string = foundryProject.name
output foundryProjectId string = foundryProject.id
output foundryProjectEndpoint string = foundryProjectEndpoint
// Keep the deployment's canonical project coordinates in the AZD environment.
// These legacy aliases are consumed by the hosted-agent CLI and release tooling.
output AZURE_AI_PROJECT_ID string = foundryProject.id
output FOUNDRY_PROJECT_ID string = foundryProject.id
output AZURE_AI_PROJECT_ENDPOINT string = foundryProjectEndpoint
output FOUNDRY_PROJECT_ENDPOINT string = foundryProjectEndpoint
output foundryNetworkInjectionCount int = enableAgentNetworkInjection ? length(foundryAccount.properties.networkInjections) : 0
output natGatewayId string = enableNat ? natGateway.id : ''
output foundryHostedResponsesUrl string = foundryHostedResponsesUrl
output foundryEventCallbackTokenSettingName string = foundryEventCallbackTokenSettingName
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output postgresFullyQualifiedDomainName string = postgresFullyQualifiedDomainName
output postgresDatabaseName string = postgresDatabaseName
output POSTGRES_SERVER_NAME string = resolvedPostgresServerName
output POSTGRES_SERVER_FQDN string = postgresFullyQualifiedDomainName
output POSTGRES_PRIVATE_DNS_ZONE_NAME string = 'privatelink.postgres.database.azure.com'
output POSTGRES_PRIVATE_ENDPOINT_NAME string = (enablePrivateEndpoints && enablePostgresPrivateEndpoint) ? postgresPrivateEndpoint!.outputs.name : ''
output accountCapabilityHost string = createAccountCapabilityHost ? addAccountCapabilityHost!.outputs.accountCapabilityHostName : ''
output projectCapabilityHost string = (createProjectCapabilityHost && manageProjectConnections) ? addProjectCapabilityHost!.outputs.projectCapabilityHostName : ''
output projectPrincipalId string = resolvedProjectPrincipalId
output projectWorkspaceId string = resolvedProjectWorkspaceId
output connectionNames object = {
  cosmos: resolvedCosmosConnectionName
  storage: resolvedStorageConnectionName
  aiSearch: resolvedAiSearchConnectionName
  applicationInsights: resolvedApplicationInsightsConnectionName
  runtimeSecrets: resolvedRuntimeConnectionName
}
output applicationInsightsConnectionId string = resolvedApplicationInsightsConnectionId
output virtualNetwork object = privateNetworking ? {
  name: virtualNetwork!.outputs.name
  id: virtualNetwork!.outputs.id
  agentSubnetId: virtualNetwork!.outputs.agentSubnetId
  privateEndpointSubnetId: virtualNetwork!.outputs.privateEndpointSubnetId
  containerAppsSubnetId: virtualNetwork!.outputs.containerAppsSubnetId
} : {
  name: ''
  id: ''
  agentSubnetId: ''
  privateEndpointSubnetId: ''
  containerAppsSubnetId: ''
}
output privateEndpointIds object = enablePrivateEndpoints ? {
  storage: storagePrivateEndpoint!.outputs.id
  aiSearch: searchPrivateEndpoint!.outputs.id
  cosmos: cosmosPrivateEndpoint!.outputs.id
  foundry: foundryPrivateEndpoint!.outputs.id
  acr: acrPrivateEndpoint!.outputs.id
  postgres: postgresPrivateEndpoint!.outputs.id
} : {
  storage: ''
  aiSearch: ''
  cosmos: ''
  foundry: ''
  acr: ''
  postgres: ''
}
output AZURE_CONTAINER_ENVIRONMENT_NAME string = enableContainerApps ? (bootstrapDeployment ? containerAppsEnvironment!.name : existingContainerAppsEnvironment!.name) : ''
output SERVICE_BACKEND_NAME string = enableContainerApps ? (bootstrapDeployment ? backendContainerApp!.name : existingBackendContainerApp!.name) : ''
output BACKEND_CONTAINER_APP_NAME string = enableContainerApps ? (bootstrapDeployment ? backendContainerApp!.name : existingBackendContainerApp!.name) : ''
output BACKEND_INTERNAL_FQDN string = enableContainerApps ? (bootstrapDeployment ? backendContainerApp!.properties.configuration.ingress.fqdn : existingBackendContainerApp!.properties.configuration.ingress.fqdn) : ''
output SERVICE_FRONTEND_NAME string = enableContainerApps ? (bootstrapDeployment ? frontendContainerApp!.name : existingFrontendContainerApp!.name) : ''
output FRONTEND_CONTAINER_APP_NAME string = enableContainerApps ? (bootstrapDeployment ? frontendContainerApp!.name : existingFrontendContainerApp!.name) : ''
output CONTAINER_APPS_ENVIRONMENT_NAME string = enableContainerApps ? (bootstrapDeployment ? containerAppsEnvironment!.name : existingContainerAppsEnvironment!.name) : ''
output WEB_URL string = enableContainerApps ? 'https://${resolvedFrontendFqdn}' : ''
output aiSearchTopologyWarning string = (privateNetworking && isCrossRegionAiSearch) ? 'WARNING: AI Search location differs from deployment location; this introduces a cross-region private-link data path and should be reviewed for latency/residency requirements.' : ''
output privateRunnerAccess object = enablePrivateRunnerAccess ? {
  enabled: true
  runnerSubnetId: privateRunnerAccess!.outputs.runnerSubnetId
  bastionSubnetId: privateRunnerAccess!.outputs.bastionSubnetId
  runnerVmId: privateRunnerAccess!.outputs.runnerVmId
  runnerVmPrincipalId: privateRunnerAccess!.outputs.runnerVmPrincipalId
  runnerUamiId: privateRunnerAccess!.outputs.runnerUamiId
  runnerUamiPrincipalId: privateRunnerAccess!.outputs.runnerUamiPrincipalId
  runnerUamiClientId: privateRunnerAccess!.outputs.runnerUamiClientId
  bastionHostId: privateRunnerAccess!.outputs.bastionHostId
  bastionPublicIpId: privateRunnerAccess!.outputs.bastionPublicIpId
} : {
  enabled: false
  runnerSubnetId: ''
  bastionSubnetId: ''
  runnerVmId: ''
  runnerVmPrincipalId: ''
  runnerUamiId: ''
  runnerUamiPrincipalId: ''
  runnerUamiClientId: ''
  bastionHostId: ''
  bastionPublicIpId: ''
}
output PRIVATE_RUNNER_VM_NAME string = enablePrivateRunnerAccess ? runnerVmName : ''
output requiredBackendSettings array = [
  'FOUNDRY_PROJECTS_ENDPOINT=${foundryProjectEndpoint}'
]
output deploymentContext object = {
  subscriptionId: subscription().subscriptionId
  tenantId: tenant().tenantId
  resourceGroupName: resourceGroup().name
  resourceGroupId: resourceGroup().id
  azdEnvironmentName: azdEnvironmentName
  deploymentMode: deploymentMode
  namePrefix: namePrefix
  locations: {
    foundry: location
    aiSearch: aiSearchLocation
    cosmos: cosmosLocation
    postgres: postgresLocation
  }
  foundryAccountId: foundryAccount.id
  foundryProjectId: foundryProject.id
  foundryProjectEndpoint: foundryProjectEndpoint
  hostedResponsesEndpoint: foundryHostedResponsesUrl
  postgresServerName: resolvedPostgresServerName
  postgresFqdn: postgresFullyQualifiedDomainName
  containerRegistryName: containerRegistry.name
  virtualNetworkName: effectiveVirtualNetworkName
}
output nextStep string = 'Run azd deploy order-resolution-hosted, then azd ai agent invoke with responses protocol and verify Foundry + App Insights telemetry.'
