## Script to train the model on FFHQ dataset

python train.py --hps fewshot \
    --save_dir /scratch/qmd/imle/results/ffhq/ \
    --data_root /scratch/qmd/datasets/ffhq/ \
    --dataset flowers102-i \
    --lr 0.0002 