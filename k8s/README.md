# Kubernetes Deployment Guide

## Cluster Requirements

- 1 Master node
- 4 Worker nodes (2 with GPU, 2 without)
- GPU nodes labeled with `gpu=true`
- NVIDIA GPU Operator installed on GPU nodes
- Ingress controller (nginx-ingress recommended)
- Storage class for PVCs

## Prerequisites

### 1. Label GPU Nodes

```bash
# Label your GPU nodes
kubectl label nodes <gpu-node-1> gpu=true
kubectl label nodes <gpu-node-2> gpu=true

# Verify labels
kubectl get nodes --show-labels | grep gpu
```

### 2. Install NVIDIA GPU Operator

```bash
# Add NVIDIA Helm repo
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# Install GPU Operator
helm install --wait --generate-name \
  -n gpu-operator --create-namespace \
  nvidia/gpu-operator
```

### 3. Install Ingress Controller (if not already installed)

```bash
# Install nginx-ingress
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

## Build and Push Docker Image

```bash
# Build the image
docker build -t your-registry/asr-nmt-serve:latest .

# Push to your registry
docker push your-registry/asr-nmt-serve:latest
```

## Configuration

### 1. Update Secrets

Edit `k8s/secrets.yaml` with your production values:

```yaml
stringData:
  POSTGRES_PASSWORD: "P4ssword@321"
  DATABASE_URL: "postgresql+asyncpg://asr_user:P4ssword@321@postgres:5432/asr_nmt_db"
  SECRET_KEY: "your-secure-random-key"
  ADMIN_API_KEY: "will-create-later"
  MINIO_ROOT_PASSWORD: "P4ssword@321_minio"
  MINIO_SECRET_KEY: "P4ssword@321_minio"
```

### 2. Update Image Registry

Edit `k8s/kustomization.yaml`:

```yaml
images:
  - name: your-registry/asr-nmt-serve
    newName: your-actual-registry/asr-nmt-serve
    newTag: v1.0.0
```

Or use kustomize command:

```bash
cd k8s
kustomize edit set image your-registry/asr-nmt-serve=your-actual-registry/asr-nmt-serve:v1.0.0
```

### 3. Update Ingress Domain

Edit `k8s/api.yaml` and update the Ingress host:

```yaml
spec:
  rules:
    - host: asr-nmt.your-actual-domain.com
```

### 4. Update Storage Class

If your cluster uses a different storage class, update PVCs in:
- `postgres.yaml`
- `redis.yaml`
- `minio.yaml`
- `worker-gpu.yaml`

## Deployment

### Using Kustomize

```bash
# Preview what will be deployed
kubectl kustomize k8s/

# Deploy everything
kubectl apply -k k8s/

# Or step by step
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/minio.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/worker-gpu.yaml
kubectl apply -f k8s/worker-cpu.yaml
kubectl apply -f k8s/celery-beat.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/network-policy.yaml
```

### Verify Deployment

```bash
# Check all pods
kubectl get pods -n asr-nmt

# Check services
kubectl get svc -n asr-nmt

# Check ingress
kubectl get ingress -n asr-nmt

# Check GPU worker is on GPU node
kubectl get pods -n asr-nmt -o wide | grep gpu

# Check logs
kubectl logs -n asr-nmt -l app=asr-nmt-api --tail=100
kubectl logs -n asr-nmt -l app=asr-nmt-worker-gpu --tail=100
```

### Create Admin API Key

```bash
# Port-forward to API
kubectl port-forward -n asr-nmt svc/asr-nmt-api 8000:8000

# In another terminal, run the script
# (You'll need to exec into the pod or run locally with DB access)
kubectl exec -it -n asr-nmt deployment/asr-nmt-api -- python scripts/create_admin_key.py
```

## Scaling

### Manual Scaling

```bash
# Scale API replicas
kubectl scale deployment asr-nmt-api -n asr-nmt --replicas=4

# Scale CPU workers
kubectl scale deployment asr-nmt-worker-cpu -n asr-nmt --replicas=4

# GPU workers are limited by number of GPU nodes (2)
kubectl scale deployment asr-nmt-worker-gpu -n asr-nmt --replicas=2
```

### Autoscaling

HPA is configured for API and CPU workers. For queue-based scaling, consider installing KEDA:

```bash
# Install KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace
```

## Monitoring

### Check Resource Usage

```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -n asr-nmt

# GPU usage (on GPU nodes)
kubectl exec -it -n asr-nmt <gpu-worker-pod> -- nvidia-smi
```

### View Logs

```bash
# API logs
kubectl logs -n asr-nmt -l app=asr-nmt-api -f

# GPU worker logs
kubectl logs -n asr-nmt -l app=asr-nmt-worker-gpu -f

# All logs with stern (if installed)
stern -n asr-nmt .
```

## Troubleshooting

### GPU Worker Not Starting

1. Check GPU node labels:
   ```bash
   kubectl get nodes -l gpu=true
   ```

2. Check GPU operator:
   ```bash
   kubectl get pods -n gpu-operator
   ```

3. Check GPU resources:
   ```bash
   kubectl describe node <gpu-node> | grep -A 10 "Allocatable"
   ```

### Database Connection Issues

1. Check postgres is running:
   ```bash
   kubectl get pods -n asr-nmt -l app=postgres
   ```

2. Check connectivity:
   ```bash
   kubectl exec -it -n asr-nmt deployment/asr-nmt-api -- \
     python -c "from src.db.session import engine; print('Connected!')"
   ```

### Model Download Slow

Models are downloaded on first startup. To speed up:

1. Use a persistent volume for model cache
2. Pre-download models in the Docker image
3. Use init containers to download models before workers start

## Cleanup

```bash
# Delete all resources
kubectl delete -k k8s/

# Or delete namespace (removes everything)
kubectl delete namespace asr-nmt
```
