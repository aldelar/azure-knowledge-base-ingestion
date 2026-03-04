// ---------------------------------------------------------------------------
// Module: alerts.bicep
// Provisions Azure Monitor alerting for KB Agent evaluation & operations:
//   - Action Group with email receiver
//   - Sustained latency degradation alert
//   - Evaluation failure/regression signal alert
//   - Safety (red-team risk finding) signal alert
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Email address for alert notifications')
param alertEmailAddress string = ''

@description('Application Insights resource ID (alert scope)')
param appInsightsId string

@description('Log Analytics workspace resource ID (alert scope)')
param logAnalyticsWorkspaceId string

// ---------------------------------------------------------------------------
// Action Group — email receiver for all evaluation alerts
// ---------------------------------------------------------------------------
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-eval-${baseName}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'EvalAlerts'
    enabled: true
    emailReceivers: !empty(alertEmailAddress) ? [
      {
        name: 'eval-admin'
        emailAddress: alertEmailAddress
        useCommonAlertSchema: true
      }
    ] : []
  }
}

// ---------------------------------------------------------------------------
// Alert: Sustained Latency Degradation
// Fires when agent P95 request duration exceeds 30s over a 15-min window.
// Uses Application Insights requests table via log-based alert.
// ---------------------------------------------------------------------------
resource latencyAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-latency-${baseName}'
  location: location
  tags: tags
  properties: {
    displayName: 'KB Agent Latency Degradation (${baseName})'
    description: 'Agent P95 request duration exceeded 30s over a 15-min window'
    severity: 2 // Warning
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [
      appInsightsId
    ]
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where timestamp > ago(15m)
            | where cloud_RoleName contains "agent" or name contains "agent"
            | summarize p95_duration_ms = percentile(duration, 95)
            | where p95_duration_ms > 30000
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 3
            minFailingPeriodsToAlert: 2
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
  }
}

// ---------------------------------------------------------------------------
// Alert: Evaluation Failure / Regression Signal
// Fires when evaluation logs show scores below threshold.
// Monitors customEvents from the evaluation SDK in App Insights.
// ---------------------------------------------------------------------------
resource evalRegressionAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-eval-regression-${baseName}'
  location: location
  tags: tags
  properties: {
    displayName: 'KB Agent Eval Regression (${baseName})'
    description: 'Evaluation scores dropped below acceptable thresholds in the last 24h'
    severity: 2 // Warning
    enabled: true
    evaluationFrequency: 'PT1H'
    windowSize: 'PT24H'
    scopes: [
      logAnalyticsWorkspaceId
    ]
    criteria: {
      allOf: [
        {
          query: '''
            AppTraces
            | where TimeGenerated > ago(24h)
            | where Message contains "evaluation" and Message contains "score"
            | extend score = todouble(extract("score[\":]\\s*(\\d+\\.?\\d*)", 1, Message))
            | where isnotnull(score) and score < 3.0
            | summarize low_score_count = count()
            | where low_score_count > 5
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
  }
}

// ---------------------------------------------------------------------------
// Alert: Red-Team Safety Risk Finding
// Fires when red-team traces indicate safety violations.
// ---------------------------------------------------------------------------
resource safetyAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-safety-${baseName}'
  location: location
  tags: tags
  properties: {
    displayName: 'KB Agent Safety Risk Finding (${baseName})'
    description: 'Red-team or safety evaluator flagged a risk finding in the last 24h'
    severity: 1 // Error
    enabled: true
    evaluationFrequency: 'PT1H'
    windowSize: 'PT24H'
    scopes: [
      logAnalyticsWorkspaceId
    ]
    criteria: {
      allOf: [
        {
          query: '''
            AppTraces
            | where TimeGenerated > ago(24h)
            | where Message contains "violence" or Message contains "hate" or Message contains "sexual" or Message contains "self_harm"
            | where Message contains "high" or Message contains "medium"
            | summarize safety_findings = count()
            | where safety_findings > 0
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output actionGroupId string = actionGroup.id
output actionGroupName string = actionGroup.name
output latencyAlertId string = latencyAlert.id
output evalRegressionAlertId string = evalRegressionAlert.id
output safetyAlertId string = safetyAlert.id
