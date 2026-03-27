#!/usr/bin/env bash
# scripts/dev-setup-gpu.sh — Configure Docker GPU support for local Linux engines.
# Run via: sudo make dev-setup-gpu

set -euo pipefail

readonly WSL_NVIDIA_SMI="/usr/lib/wsl/lib/nvidia-smi"
readonly NVIDIA_KEYRING="/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"
readonly NVIDIA_APT_LIST="/etc/apt/sources.list.d/nvidia-container-toolkit.list"
readonly NVIDIA_CDI_SPEC="/etc/cdi/nvidia.yaml"
readonly CUDA_TEST_IMAGE="nvidia/cuda:12.4.1-base-ubuntu22.04"

require_root() {
    if [[ ${EUID} -ne 0 ]]; then
        echo "Run 'sudo make dev-setup-gpu'." >&2
        exit 1
    fi
}

has_command() {
    command -v "$1" >/dev/null 2>&1
}

is_wsl() {
    grep -qi microsoft /proc/version 2>/dev/null || [[ -e /dev/dxg ]]
}

is_debian_family() {
    [[ -f /etc/debian_version ]]
}

nvidia_smi_path() {
    if has_command nvidia-smi; then
        command -v nvidia-smi
        return 0
    fi

    if [[ -x "${WSL_NVIDIA_SMI}" ]]; then
        printf '%s\n' "${WSL_NVIDIA_SMI}"
        return 0
    fi

    return 1
}

has_nvidia_gpu() {
    local nvidia_smi

    nvidia_smi="$(nvidia_smi_path 2>/dev/null)" || return 1
    "${nvidia_smi}" -L >/dev/null 2>&1
}

docker_backend() {
    local operating_system

    if ! has_command docker; then
        printf 'missing\n'
        return 0
    fi

    operating_system="$(docker info --format '{{.OperatingSystem}}' 2>/dev/null || true)"
    if [[ -z "${operating_system}" ]]; then
        printf 'unavailable\n'
    elif grep -qi 'Docker Desktop' <<<"${operating_system}"; then
        printf 'docker-desktop\n'
    else
        printf 'local-engine\n'
    fi
}

validate_docker_gpu_support() {
    echo "  gpu         validating Docker GPU access..."
    docker run --rm --gpus all "${CUDA_TEST_IMAGE}" nvidia-smi >/dev/null
}

ensure_nvidia_toolkit_repo() {
    if apt-cache policy nvidia-container-toolkit 2>/dev/null | grep -q 'Candidate:' && \
        ! apt-cache policy nvidia-container-toolkit 2>/dev/null | grep -q 'Candidate: (none)'; then
        return
    fi

    if ! has_command curl; then
        apt-get update
        apt-get install -y curl
    fi

    if ! has_command gpg; then
        apt-get update
        apt-get install -y gpg
    fi

    echo "  gpu         adding NVIDIA container toolkit apt repository..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        gpg --dearmor --yes -o "${NVIDIA_KEYRING}"
    curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' > "${NVIDIA_APT_LIST}"
    apt-get update
}

install_nvidia_container_toolkit() {
    if has_command nvidia-ctk; then
        echo "  gpu         NVIDIA container toolkit already installed ($(nvidia-ctk --version 2>&1 | head -1))"
        return
    fi

    ensure_nvidia_toolkit_repo
    echo "  gpu         installing NVIDIA container toolkit..."
    apt-get install -y nvidia-container-toolkit
}

restart_docker_service() {
    echo "  gpu         restarting Docker to pick up NVIDIA runtime changes..."

    if has_command systemctl && systemctl status docker >/dev/null 2>&1; then
        systemctl restart docker
        return
    fi

    if has_command service; then
        service docker restart
        return
    fi

    echo "  gpu         unable to restart Docker automatically; restart dockerd manually before retrying validation." >&2
}

configure_local_docker_gpu_runtime() {
    install_nvidia_container_toolkit

    echo "  gpu         configuring Docker runtime and CDI for NVIDIA containers..."
    mkdir -p /etc/cdi
    nvidia-ctk runtime configure --runtime=docker
    nvidia-ctk cdi generate --output="${NVIDIA_CDI_SPEC}"
    restart_docker_service
}

main() {
    local backend

    require_root

    echo "Configuring Docker GPU support..."

    if ! has_nvidia_gpu; then
        echo "  gpu         no NVIDIA GPU detected in this Linux environment; nothing to configure."
        return
    fi

    backend="$(docker_backend)"
    case "${backend}" in
        missing)
            echo "  gpu         Docker is not installed; install Docker first." >&2
            exit 1
            ;;
        unavailable)
            echo "  gpu         Docker is installed but the daemon is not reachable; start Docker first." >&2
            exit 1
            ;;
        docker-desktop)
            if is_wsl; then
                echo "  gpu         WSL + Docker Desktop engine detected; Linux-side NVIDIA toolkit setup is not required here."
                if validate_docker_gpu_support; then
                    echo "  gpu         Docker Desktop GPU passthrough is already working."
                    return
                fi

                echo "  gpu         Docker Desktop GPU passthrough is still failing. Fix it in Docker Desktop and Windows, then retry." >&2
                exit 1
            fi
            ;;
    esac

    if ! is_debian_family; then
        echo "  gpu         automatic NVIDIA toolkit installation is only implemented for Debian/Ubuntu hosts." >&2
        exit 1
    fi

    if validate_docker_gpu_support; then
        echo "  gpu         Docker GPU support is already working."
        return
    fi

    if is_wsl; then
        echo "  gpu         WSL with a local Docker Engine detected; configuring NVIDIA container support inside this distro."
    else
        echo "  gpu         Native Linux Docker Engine detected; configuring NVIDIA container support on this host."
    fi

    configure_local_docker_gpu_runtime

    if validate_docker_gpu_support; then
        echo "  gpu         Docker GPU validation passed. Ollama can use the NVIDIA GPU."
        return
    fi

    echo "  gpu         Docker GPU validation still failed after configuration. Re-check the host NVIDIA driver and Docker daemon logs." >&2
    exit 1
}

main "$@"