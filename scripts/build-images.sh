#!/bin/bash
# Build script for ASR-NMT Docker images

set -e

REGISTRY=${REGISTRY:-"your-registry"}
TAG=${TAG:-"latest"}

echo "Building ASR-NMT images..."
echo "Registry: $REGISTRY"
echo "Tag: $TAG"

# Build CPU image (for API and CPU workers)
echo ""
echo "=== Building CPU image ==="
docker build \
    --target base \
    -t ${REGISTRY}/asr-nmt-serve:${TAG} \
    -t ${REGISTRY}/asr-nmt-serve:cpu-${TAG} \
    .

# Build GPU image (for GPU workers)
echo ""
echo "=== Building GPU image ==="
docker build \
    --target gpu \
    -t ${REGISTRY}/asr-nmt-serve:gpu-${TAG} \
    .

echo ""
echo "=== Images built successfully ==="
echo "CPU image: ${REGISTRY}/asr-nmt-serve:${TAG}"
echo "GPU image: ${REGISTRY}/asr-nmt-serve:gpu-${TAG}"

# Push if PUSH=true
if [ "$PUSH" = "true" ]; then
    echo ""
    echo "=== Pushing images ==="
    docker push ${REGISTRY}/asr-nmt-serve:${TAG}
    docker push ${REGISTRY}/asr-nmt-serve:cpu-${TAG}
    docker push ${REGISTRY}/asr-nmt-serve:gpu-${TAG}
    echo "Images pushed successfully!"
fi

echo ""
echo "To push images manually:"
echo "  docker push ${REGISTRY}/asr-nmt-serve:${TAG}"
echo "  docker push ${REGISTRY}/asr-nmt-serve:gpu-${TAG}"
