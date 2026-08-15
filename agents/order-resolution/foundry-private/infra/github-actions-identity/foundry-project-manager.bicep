targetScope = 'resourceGroup'

@description('Object ID of the protected private-release service principal.')
param deploymentPrincipalId string

@description('Foundry account that hosts the protected private release project.')
param foundryAccountName string

@description('Foundry project that receives the hosted-agent deployment role.')
param foundryProjectName string = 'order-resolution'

@description('Private ACR that receives the hosted-agent image.')
param containerRegistryName string

var foundryProjectManagerRoleDefinitionId = 'eadc314b-1a2d-4efa-be10-5d325db5065e'
var acrPushRoleDefinitionId = '8311e382-0749-4cb8-b61a-304f252e45ec'

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

resource foundryProjectManagerRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryProject.id, deploymentPrincipalId, foundryProjectManagerRoleDefinitionId)
  scope: foundryProject
  properties: {
    principalId: deploymentPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryProjectManagerRoleDefinitionId)
  }
}

resource releaseAcrPushRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, deploymentPrincipalId, acrPushRoleDefinitionId)
  scope: containerRegistry
  properties: {
    principalId: deploymentPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPushRoleDefinitionId)
  }
}
