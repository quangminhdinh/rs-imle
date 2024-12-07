## Script to train the model on FFHQ dataset

python train.py --hps fewshot \
    --save_dir ./new-vanilla-results/ffhq/ \
    --data_root ./datasets/ffhq/ \
    --lr 0.0002 