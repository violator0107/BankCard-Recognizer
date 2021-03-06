import os
import random

import cv2
import numpy as np
from tqdm import tqdm

from aug import DataAugmentation


def train_val_split(src_dir, val_split_ratio=0.15):
    # Prepare a whole list of images and labels.
    data_path, labels = [], []
    for file in os.listdir(src_dir):
        data_path.append(src_dir + file)
        name, ext = os.path.splitext(file)
        labels.append(name[:4])

    # Select val-set by index randomly.
    length = len(data_path)
    rand_index = list(range(length))
    random.shuffle(rand_index)
    val_index = rand_index[0: int(val_split_ratio * length)]

    # Collect them and return.
    train_set, val_set = [], []
    for i in range(length):
        if i in val_index:
            val_set.append((data_path[i], labels[i]))
        else:
            train_set.append((data_path[i], labels[i]))
    return train_set, val_set


def data_wrapper(src_list, img_shape, max_label_length,
                 max_aug_nbr=1, aug_param_dict=None, name="temp"):
    """
    When fetching data to the training generator,
    the DataGenerator will select one batch from Pool randomly.
    So generate(or with augmentation) all the necessary data to DataGenerator.
    However, you cannot deliver the augment data directly,
    nor the training foreplay will be endless till you run out of your Memories.
    So save it on the local disk in .npz format with a name,
    the DataGenerator will read it, thus will save a lot of unnecessary costs.

    :param src_list: Selected train/val img path with form (path, label).
    :param img_shape: Image shape (width, height)
    :param max_aug_nbr: Max number of doing augmentation.
    :param max_label_length: Max number of label length.
    :param aug_param_dict: A dict for saving data-augmentation parameters.
                           With code:
                           'hsr': height_shift_range      'wsr': width_shift_range
                           'ror': rotate_range            'zor': zoom_range            'shr': shear_range
                           'hfl': horizontal_flip         'vfl': vertical_flip
                           'nof': noise_factor            'blr': blur_factor
    :param name: Providing a name for this wrapper.
    :return: data, labels, labels_length or local_path.
    """

    # Initialize some variables
    n = len(src_list) * max_aug_nbr
    img_w, img_h = img_shape
    is_saved = False
    # Status progress bar.
    p_bar = tqdm(total=len(src_list))
    # Create random indexes.
    rand_index = np.random.permutation(n)

    data = np.zeros((n, img_h, img_w))
    labels = np.zeros((n, max_label_length))
    labels_length = np.zeros((n, 1))

    def valid_img(image):
        # Do some common process to image.
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image = cv2.resize(image, img_shape)
        image = image.astype(np.float32)
        return image

    def valid_label(label_string):
        # Get rid of the empty placeholder '_'.
        # Even it is the head of label.
        res = []
        for ch in label_string:
            if ch == '_':
                continue
            else:
                res.append(int(ch))
        a = len(res)
        for i in range(max_label_length - a):
            res.append(10)  # represent '_'
        # Return res for labels, length for labels_length
        return res, a

    index = 0
    for path, label in src_list:
        img = cv2.imread(path)
        v_lab, v_len = valid_label(label)
        data[rand_index[index]] = valid_img(img)
        labels[rand_index[index]] = v_lab
        labels_length[rand_index[index]][0] = v_len

        if max_aug_nbr != 1 and aug_param_dict is not None and any(aug_param_dict):
            is_saved = True
            # Once trigger the data augmentation, it will be saved in local.
            aug = DataAugmentation(img, aug_param_dict)
            # max_aug_nbr = original_img(.also 1) + augment_img
            for aug_img in aug.feed(max_aug_nbr-1):
                index += 1
                data[rand_index[index]] = valid_img(aug_img)
                # Different augmentation of images, but same labels and length.
                labels[rand_index[index]] = v_lab
                labels_length[rand_index[index]][0] = v_len
        index += 1
        p_bar.update()
    p_bar.close()
    data.astype(np.float64) / 255.0 * 2 - 1
    data = np.expand_dims(data, axis=-1)
    labels.astype(np.float64)

    if is_saved:
        local_path = "%s.npz" % name
        np.savez(local_path, data=data, labels=labels, labels_length=labels_length)
        print("[*] Data with augmentation has been saved in local disk.")
        return local_path
    else:
        return data, labels, labels_length
