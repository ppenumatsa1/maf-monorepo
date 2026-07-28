targetScope = 'resourceGroup'

extension microsoftGraphV1

@description('GitHub owner/repository trusted by the deployment identity.')
param githubRepository string = 'ppenumatsa1/maf-monorepo'

@description('Exact GitHub OIDC subject emitted for the protected private-release environment.')
param githubSubject string = 'repo:ppenumatsa1@37847579/maf-monorepo@1314177122:environment:foundry-private-env'

@description('Immutable Microsoft Graph alternate key for the deployment application.')
param applicationUniqueName string = 'maf-ora-github-private-v2'

var applicationDisplayName = 'maf-ora-github-private-v2'
var federatedCredentialName = 'github-maf-monorepo-foundry-private-env'
var githubIssuer = 'https://token.actions.githubusercontent.com'
var azureTokenExchangeAudience = 'api://AzureADTokenExchange'

resource githubActionsApplication 'Microsoft.Graph/applications@v1.0' = {
  displayName: applicationDisplayName
  uniqueName: applicationUniqueName

  resource githubFederatedCredential 'federatedIdentityCredentials@v1.0' = {
    name: '${githubActionsApplication.uniqueName}/${federatedCredentialName}'
    description: 'Trust the protected private release environment in ${githubRepository}.'
    audiences: [
      azureTokenExchangeAudience
    ]
    issuer: githubIssuer
    subject: githubSubject
  }
}

resource githubActionsServicePrincipal 'Microsoft.Graph/servicePrincipals@v1.0' = {
  appId: githubActionsApplication.appId
}

var contributorRoleDefinitionId = 'b24988ac-6180-42a0-ab88-20f7382dd24c'
var userAccessAdministratorRoleDefinitionId = '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9'

resource contributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, applicationUniqueName, contributorRoleDefinitionId)
  properties: {
    principalId: githubActionsServicePrincipal.id
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributorRoleDefinitionId)
  }
}

resource userAccessAdministratorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, applicationUniqueName, userAccessAdministratorRoleDefinitionId)
  properties: {
    principalId: githubActionsServicePrincipal.id
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', userAccessAdministratorRoleDefinitionId)
  }
}

output githubActionsClientId string = githubActionsApplication.appId
output githubActionsPrincipalId string = githubActionsServicePrincipal.id
output githubActionsFederatedSubject string = githubSubject
