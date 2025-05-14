## Script to train the model on FFHQ dataset

uv run train.py --hps fewshot \
    --save_dir ./new-vanilla-results/ffhq/ \
    --data_root ./datasets/ffhq/ \
    --dataset ffhq_256
    --lr 0.0002 
