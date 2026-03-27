#!/usr/bin/env bash
# scripts/dev-setup.sh — Install user-scoped development prerequisites.
# Run via: make dev-setup

set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly WSL_NVIDIA_SMI="/usr/lib/wsl/lib/nvidia-smi"
readonly CUDA_TEST_IMAGE="nvidia/cuda:12.4.1-base-ubuntu22.04"

ensure_non_root() {
    if [[ ${EUID} -eq 0 || -n "${SUDO_USER:-}" ]]; then
        echo "Run 'make dev-setup' as your normal user." >&2
        echo "If Docker GPU support is missing, run 'sudo make dev-setup-gpu' separately." >&2
        exit 1
    fi
}

has_command() {
    command -v "$1" >/dev/null 2>&1
}

is_wsl() {
    grep -qi microsoft /proc/version 2>/dev/null || [[ -e /dev/dxg ]]
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
    docker run --rm --gpus all "${CUDA_TEST_IMAGE}" nvidia-smi >/dev/null 2>&1
}

install_azure_cli() {
    if has_command az; then
        echo "  az          already installed ($(az --version 2>&1 | head -1))"
        return
    fi

    echo "  az          installing..."
    curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
}

install_azd() {
    if has_command azd; then
        echo "  azd         already installed ($(azd version 2>&1 | head -1))"
        return
    fi

    echo "  azd         installing..."
    curl -fsSL https://aka.ms/install-azd.sh | bash
}

install_uv() {
    if has_command uv; then
        echo "  uv          already installed ($(uv --version 2>&1 | head -1))"
        return
    fi

    echo "  uv          installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
}

install_functions_core_tools() {
    if has_command func; then
        echo "  func        already installed ($(func --version 2>&1 | head -1))"
        return
    fi

    echo "  func        installing..."
    npm install -g azure-functions-core-tools@4 --unsafe-perm true
}

install_playwright_browser() {
    echo ""
    echo "Installing Playwright chromium browser for UI tests..."
    cd "${REPO_ROOT}/src/web-app"
    uv run playwright install chromium
}

print_gpu_guidance() {
    local backend

    echo ""
    echo "Checking optional Docker GPU support for Ollama..."

    if ! has_nvidia_gpu; then
        echo "  gpu         no NVIDIA GPU detected in this Linux environment; Ollama will run on CPU."
        return
    fi

    backend="$(docker_backend)"
    case "${backend}" in
        missing)
            echo "  gpu         Docker is not installed yet; skipping GPU validation."
            return
            ;;
        unavailable)
            echo "  gpu         Docker is installed but the daemon is not reachable; start Docker first."
            return
            ;;
        docker-desktop)
            if is_wsl; then
                echo "  gpu         WSL + Docker Desktop engine detected; GPU support is managed by Docker Desktop on Windows."
                if validate_docker_gpu_support; then
                    echo "  gpu         Docker Desktop GPU passthrough is working."
                else
                    echo "  gpu         Docker Desktop GPU passthrough is not working yet. Check Docker Desktop WSL integration and the Windows NVIDIA driver."
                fi
                return
            fi
            ;;
    esac

    if validate_docker_gpu_support; then
        echo "  gpu         Docker GPU support is already working for the local Linux engine."
        return
    fi

    if is_wsl; then
        echo "  gpu         WSL with a local Docker Engine detected, but NVIDIA container runtime support is not configured."
    else
        echo "  gpu         Native Linux Docker Engine detected, but NVIDIA container runtime support is not configured."
    fi
    echo "  gpu         Run 'sudo make dev-setup-gpu' to install and configure the NVIDIA container toolkit."
}

main() {
    ensure_non_root

    echo "Installing development prerequisites..."
    echo ""

    install_azure_cli
    install_azd
    install_uv
    install_functions_core_tools
    install_playwright_browser
    print_gpu_guidance

    echo ""
    echo "Done. Next: copy .env.dev.template to .env.dev, then run make dev-infra-up."
}

main "$@"
