import torch
import numpy as np
from fcn_benchmark.modeling.generalized_fcn import GeneralizedFCN
import cv2
from fcn_benchmark.data.transforms import build_transforms
from collections import OrderedDict
from fcn_benchmark.utils.util import crop_weight, to_binary_mask
import pycocotools.mask as mask_utils

class Infer(object):
    def __init__(self, model_path):
        super(Infer, self).__init__()
        model = GeneralizedFCN()
        checkpoint = crop_weight(model_path)
        model.load_state_dict(checkpoint)
        model.eval()
        
        self.model = model
        self.transforms = build_transforms()

    def eval_img(self, image_arr):
        img_ori = image_arr
        dshape = (img_ori.shape[1], img_ori.shape[0])
        img = img_ori.copy()
        img = self.transforms(img)
        output = self.model(img.unsqueeze(0)).squeeze(0).squeeze(0)
        binary_mask = to_binary_mask(output, dshape)
        cv2.imshow('ori', img_ori.copy())
        cv2.imshow('test', (binary_mask[..., np.newaxis] * img_ori.copy()).astype(np.uint8))
        cv2.waitKey()

    def eval_res(self, segm, gt):
        num_mismatch = []
        iou_mismatch = []
        urls = []
        ious = []

        res_n = {}
        gt_n = {}
        for r in segm:
            res_n[r['image_id']] = r['segmentation']

        for i in gt['images']:
            gt_n[i['id']] = {'height': i['height'], 'width': i['width'],'file_name': i['file_name']}

        for a in gt['annotations']:
            if a['image_id'] not in gt_n:
                print('check your gt json.')
                raise
            height, width = gt_n[a['image_id']]['height'], gt_n[a['image_id']]['width']
            rle = mask_utils.frPyObjects(a['segmentation'], height, width)
            if 'segmentation' in gt_n:
                print('more than one segm')
            else:
                if a['image_id'] not in res_n:
                    num_mismatch.append(a['image_id'])
                    continue
                iou = mask_utils.iou([res_n[a['image_id']]], rle, [False])
                if iou[0][0] < 0.8:
                    iou_mismatch.append(a['id'])
                    urls.append(gt_n[a['image_id']]['file_name'])
                ious.append(iou[0][0])
        print('iou mismatch objs (iou<0.8):')
        print(iou_mismatch)
        with open('err.txt', 'w') as f:
            f.write('\n'.join(urls))
        print('num mismatch objs:')
        print(num_mismatch)
        print('mean iou:',torch.tensor(ious).mean().item())


if __name__=='__main__':
    import sys
    from cvtools import cv_load_image, clamp
    import argparse
    import json

    parser = argparse.ArgumentParser(description='End-to-end inference')
    parser.add_argument('--wts', '-w', default='', type=str, metavar='W')
    parser.add_argument('--segm', default='', type=str, metavar='S')
    parser.add_argument('--gt', default='', type=str, metavar='G')
    parser.add_argument('file_or_folder', help='images', default='')
    args = parser.parse_args()

    if not args.wts:
        print('need --wts argument. exit.')

    I = Infer(args.wts)
    
    if not args.segm:
        pic = args.file_or_folder
        wts = args.wts
        if pic.startswith('http'):
            img = cv_load_image(pic)
            h, w, _ = img.shape
            if w > 1280:
                r, l, img = clamp(img)
        else:
            img = cv2.imread(pic)
        I.eval_img(img)

    else:
        if args.gt:
            res = torch.load(args.segm)
            gt = json.load(open(args.gt, 'r'))
            I.eval_res(res, gt)
           
