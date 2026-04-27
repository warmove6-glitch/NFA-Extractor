@echo off
:: ============================================================
:: ORGATEC — Motor Local ms-swift
:: Inicia servidor de inferência local (OpenAI-compatible API)
:: Endpoint: http://localhost:8000/v1
:: ============================================================

set MODEL=Qwen/Qwen2.5-7B-Instruct
set PORT=8000

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   ORGATEC — Motor Local ms-swift              ║
echo  ║   Modelo: %MODEL%    ║
echo  ║   Endpoint: http://localhost:%PORT%/v1          ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Verifica se ms-swift está instalado
swift --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] ms-swift não encontrado. Instalando...
    pip install "ms-swift[llm]" -U
)

:: Detecta GPU (NVIDIA)
where nvcc >nul 2>&1
if errorlevel 1 (
    echo [INFO] GPU NVIDIA não detectada — usando backend CPU (pt)
    echo [AVISO] CPU é mais lento. Para GPU, instale CUDA e reexecute.
    echo.
    swift deploy ^
        --model %MODEL% ^
        --infer_backend pt ^
        --port %PORT% ^
        --max_new_tokens 4096
) else (
    echo [INFO] GPU NVIDIA detectada — usando backend vLLM (acelerado)
    echo.
    swift deploy ^
        --model %MODEL% ^
        --infer_backend vllm ^
        --port %PORT% ^
        --max_new_tokens 4096 ^
        --gpu_memory_utilization 0.85
)
