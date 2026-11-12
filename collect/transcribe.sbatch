#!/bin/bash
#SBATCH --job-name=kalshi_whisper
#SBATCH --account=torch_pr_60_tandon_advanced
#SBATCH --partition=l40s_public
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=/scratch/sd5963/slurm_logs/kalshi_whisper_%j.out

cd /scratch/sd5963/kalsi_palantir
nvidia-smi --query-gpu=name,memory.total --format=csv
singularity exec --nv --env HF_HOME=/scratch/sd5963/.cache/huggingface --env USER=sd5963 --env HF_HUB_OFFLINE=1 \
  --env FFMPEG=/scratch/sd5963/kalsi_palantir/.venv/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v9.0.2 \
  /scratch/sd5963/containers/w2v2_cuda_cu128.sif python3 collect/transcribe.py
