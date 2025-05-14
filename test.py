from PIL import Image
import numpy as np
import os

p = "/home/minhdq/rs-imle/datasets/100-shot-panda/img"
dat = []
flist = os.listdir(p)

for fn in flist:
    img = Image.open(os.path.join(p, fn))
    dat.append(np.asarray(img))

print(np.stack(dat).shape)
