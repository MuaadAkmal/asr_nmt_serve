#!/bin/bash
# Quick deployment script for Kubernetes

set -e

NAMESPACE=${NAMESPACE:-"asr-nmt"}
REGISTRY=${REGISTRY:-"your-registry"}
TAG=${TAG:-"latest"}

echo "Deploying ASR-NMT to Kubernetes..."
echo "Namespace: $NAMESPACE"
echo "Registry: $REGISTRY"
echo "Tag: $TAG"

# Update image in kustomization
cd k8s
kustomize edit set image your-registry/asr-nmt-serve=${REGISTRY}/asr-nmt-serve:${TAG}

# Apply all manifests
echo ""
echo "=== Applying Kubernetes manifests ==="
kubectl apply -k .

# Wait for deployments
echo ""
echo "=== Waiting for deployments ==="
kubectl rollout status deployment/postgres -n $NAMESPACE --timeout=120s
kubectl rollout status deployment/redis -n $NAMESPACE --timeout=120s
kubectl rollout status deployment/minio -n $NAMESPACE --timeout=120s
kubectl rollout status deployment/asr-nmt-api -n $NAMESPACE --timeout=300s
kubectl rollout status deployment/asr-nmt-worker-gpu -n $NAMESPACE --timeout=300s
kubectl rollout status deployment/asr-nmt-worker-cpu -n $NAMESPACE --timeout=120s
kubectl rollout status deployment/celery-beat -n $NAMESPACE --timeout=120s

echo ""
echo "=== Deployment complete ==="
kubectl get pods -n $NAMESPACE

echo ""
echo "=== Services ==="
kubectl get svc -n $NAMESPACE

echo ""
echo "=== Ingress ==="
kubectl get ingress -n $NAMESPACE
