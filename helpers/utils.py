import os
import json
import tempfile
import numpy as np
import torch
import time
import subprocess
import torch.distributed as dist
import torch.utils.data as data
from PIL import Image



def allreduce(x, average):
    if mpi_size() > 1:
        dist.all_reduce(x, dist.ReduceOp.SUM)
    return x / mpi_size() if average else x


def get_cpu_stats_over_ranks(stat_dict):
    keys = sorted(stat_dict.keys())
    allreduced = allreduce(torch.stack([torch.as_tensor(stat_dict[k]).detach().cpu().float() for k in keys]), average=True).cpu()
    return {k: allreduced[i].item() for (i, k) in enumerate(keys)}


class Hyperparams(dict):
    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            return None

    def __setattr__(self, attr, value):
        self[attr] = value


def logger(log_prefix):
    'Prints the arguments out to stdout, .txt, and .jsonl files'

    jsonl_path = f'{log_prefix}.jsonl'
    txt_path = f'{log_prefix}.txt'

    def log(*args, pprint=False, **kwargs):
        if mpi_rank() != 0:
            return
        t = time.ctime()
        argdict = {'time': t}
        if len(args) > 0:
            argdict['message'] = ' '.join([str(x) for x in args])
        argdict.update(kwargs)

        txt_str = []
        args_iter = sorted(argdict) if pprint else argdict
        for k in args_iter:
            val = argdict[k]
            if isinstance(val, np.ndarray):
                val = val.tolist()
            elif isinstance(val, np.integer):
                val = int(val)
            elif isinstance(val, np.floating):
                val = float(val)
            argdict[k] = val
            if isinstance(val, float):
                val = f'{val:.5f}'
            txt_str.append(f'{k}: {val}')
        txt_str = ', '.join(txt_str)

        if pprint:
            json_str = json.dumps(argdict, sort_keys=True)
            txt_str = json.dumps(argdict, sort_keys=True, indent=4)
        else:
            json_str = json.dumps(argdict)

        print(txt_str, flush=True)

        with open(txt_path, "a+") as f:
            print(txt_str, file=f, flush=True)
        with open(jsonl_path, "a+") as f:
            print(json_str, file=f, flush=True)

    return log


def maybe_download(path, filename=None):
    '''If a path is a gsutil path, download it and return the local link,
    otherwise return link'''
    if not path.startswith('gs://'):
        return path
    if filename:
        local_dest = f'/tmp/'
        out_path = f'/tmp/{filename}'
        if os.path.isfile(out_path):
            return out_path
        subprocess.check_output(['gsutil', '-m', 'cp', '-R', path, out_path])
        return out_path
    else:
        local_dest = tempfile.mkstemp()[1]
        subprocess.check_output(['gsutil', '-m', 'cp', path, local_dest])
    return local_dest


def tile_images(images, d1=4, d2=4, border=1):
    id1, id2, c = images[0].shape
    out = np.ones([d1 * id1 + border * (d1 + 1),
                   d2 * id2 + border * (d2 + 1),
                   c], dtype=np.uint8)
    out *= 255
    if len(images) != d1 * d2:
        raise ValueError('Wrong num of images')
    for imgnum, im in enumerate(images):
        num_d1 = imgnum // d2
        num_d2 = imgnum % d2
        start_d1 = num_d1 * id1 + border * (num_d1 + 1)
        start_d2 = num_d2 * id2 + border * (num_d2 + 1)
        out[start_d1:start_d1 + id1, start_d2:start_d2 + id2, :] = im
    return out


def mpi_size():
    return 0


def mpi_rank():
    return 0


def num_nodes():
    nn = mpi_size()
    if nn % 8 == 0:
        return nn // 8
    return nn // 8 + 1


def gpus_per_node():
    size = mpi_size()
    if size > 1:
        return max(size // num_nodes(), 1)
    return 1


def local_mpi_rank():
    return mpi_rank() % gpus_per_node()


def pad_resize(img, size):
    h, w, _ = img.shape
    if h > w:
        gap = h - w
        side = gap // 2
        img_t = np.pad(img, ((0, 0), (side, gap - side), (0, 0)))
    elif w > h:
        gap = w - h
        side = gap // 2
        img_t = np.pad(img, ((side, gap - side), (0, 0), (0, 0)))
    else:
        img_t = img
    im = Image.fromarray(img_t)
    im2 = im.resize((size, size))
    return np.asarray(im2)


def crop_resize(img, size):
    h, w, _ = img.shape
    if h > w:
        gap = h - w
        side = gap // 2
        img_t = img[side : side + w, ...]
    elif w > h:
        gap = w - h
        side = gap // 2
        img_t = img[:, side : side + h, :]
    else:
        img_t = img
    assert img_t.shape[0] == img_t.shape[1]
    im = Image.fromarray(img_t)
    im2 = im.resize((size, size))
    return np.asarray(im2)


# def printGPUInfo(prefix=""):
#     print(prefix, end=" ")
#     deviceCount = pynvml.nvmlDeviceGetCount()
#     for i in range(deviceCount):
#         handle = pynvml.nvmlDeviceGetHandleByIndex(i)
#         meminfo = pynvml.nvmlDeviceGetMemoryInfo(handle)
#         print("GPU %d used: %d MB" % (i, meminfo.used/1048576), end=" ")
#     print()


class ZippedDataset(data.Dataset):

    def __init__(self, *datasets):
        assert all(len(datasets[0]) == len(dataset) for dataset in datasets)
        self.datasets = datasets

    def __getitem__(self, index):
        # print(index, [len(x) for x in self.datasets])
        return tuple(dataset[index] for dataset in self.datasets), index

    def __len__(self):
        return len(self.datasets[0])

