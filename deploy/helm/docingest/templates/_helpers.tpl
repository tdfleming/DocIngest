{{/* Chart name (optionally overridden). */}}
{{- define "docingest.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Fully qualified app name used as the resource-name prefix. */}}
{{- define "docingest.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "docingest.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Common labels applied to every resource. */}}
{{- define "docingest.labels" -}}
helm.sh/chart: {{ include "docingest.chart" . }}
{{ include "docingest.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* Base selector labels (extend with app.kubernetes.io/component per workload). */}}
{{- define "docingest.selectorLabels" -}}
app.kubernetes.io/name: {{ include "docingest.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Name of the API Service (defaults to `ingestion-api` for the frontend proxy). */}}
{{- define "docingest.apiServiceName" -}}
{{- default "ingestion-api" .Values.api.service.name -}}
{{- end -}}

{{/* Secret name: an existing secret if provided, else the chart-managed one. */}}
{{- define "docingest.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "docingest.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/* Bundled datastore service names. */}}
{{- define "docingest.mongodb.fullname" -}}{{ printf "%s-mongodb" (include "docingest.fullname" .) }}{{- end -}}
{{- define "docingest.qdrant.fullname" -}}{{ printf "%s-qdrant" (include "docingest.fullname" .) }}{{- end -}}
{{- define "docingest.redis.fullname" -}}{{ printf "%s-redis" (include "docingest.fullname" .) }}{{- end -}}
{{- define "docingest.minio.fullname" -}}{{ printf "%s-minio" (include "docingest.fullname" .) }}{{- end -}}

{{/* imagePullSecrets block. */}}
{{- define "docingest.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}
