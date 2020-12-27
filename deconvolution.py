#!/usr/bin/env python

'''
Wiener deconvolution.
Sample shows how DFT can be used to perform Weiner deconvolution [1]
of an image with user-defined point spread function (PSF)
Usage:
  deconvolution.py  [--circle]
      [--angle <degrees>]
      [--d <diameter>]
      [--snr <signal/noise ratio in db>]
      [<input image>]
  Use sliders to adjust PSF paramitiers.
  Keys:
    SPACE - switch btw linear/circular PSF
    ESC   - exit
Examples:
  deconvolution.py --angle 135 --d 22  licenseplate_motion.jpg
    (image source: http://www.topazlabs.com/infocus/_images/licenseplate_compare.jpg)
  deconvolution.py --angle 86 --d 31  text_motion.jpg
  deconvolution.py --circle --d 19  text_defocus.jpg
    (image source: compact digital photo camera, no artificial distortion)
[1] http://en.wikipedia.org/wiki/Wiener_deconvolution
'''

# Python 2/3 compatibility
from __future__ import print_function

import numpy as np
import cv2 as cv

# local module
#from common import nothing


def blur_edge(img, d=31):
    h, w  = img.shape[:2]
    img_pad = cv.copyMakeBorder(img, d, d, d, d, cv.BORDER_WRAP)
    img_blur = cv.GaussianBlur(img_pad, (2*d+1, 2*d+1), -1)[d:-d,d:-d]
    y, x = np.indices((h, w))
    dist = np.dstack([x, w-x-1, y, h-y-1]).min(-1)
    w = np.minimum(np.float32(dist)/d, 1.0)
    return img*w + img_blur*(1-w)

def motion_kernel(angle, d, sz=65):
    kern = np.ones((1, d), np.float32)
    c, s = np.cos(angle), np.sin(angle)
    A = np.float32([[c, -s, 0], [s, c, 0]])
    sz2 = sz // 2
    A[:,2] = (sz2, sz2) - np.dot(A[:,:2], ((d-1)*0.5, 0))
    kern = cv.warpAffine(kern, A, (sz, sz), flags=cv.INTER_CUBIC)
    return kern

def defocus_kernel(d, sz=65):
    kern = np.zeros((sz, sz), np.uint8)
    cv.circle(kern, (sz, sz), d, 255, -1, cv.LINE_AA, shift=1)
    kern = np.float32(kern) / 255.0
    return kern


def main():
    import sys, getopt
    opts, args = getopt.getopt(sys.argv[1:], '', ['circle', 'angle=', 'd=', 'snr=', 'img='])
    opts = dict(opts)
    try:
        fn = args[0]
    except:
        fn = 'car_motion.JPG'

    win = 'deconvolution'

    img_bw = cv.imread(cv.samples.findFile(fn), cv.IMREAD_GRAYSCALE)
    img_color = cv.imread(cv.samples.findFile(fn), cv.IMREAD_COLOR)

    img_bw = cv.resize(img_bw, dsize=(640, 480))
    img_color = cv.resize(img_color, dsize=(640, 480))

    if img_bw is None and img_color is None:
        print('Failed to load file:', fn)
        sys.exit(1)

    img_bw = np.float32(img_bw)/255.0

    roi_bw = cv.selectROI(img_bw)
    roi_color = cv.selectROI(img_color)

    imCropped_bw = img_bw[int(roi_bw[1]):int(roi_bw[1]+roi_bw[3]), int(roi_bw[0]):int(roi_bw[0]+roi_bw[2])]
    imCropped_color = img_color[int(roi_color[1]):int(roi_color[1]+roi_color[3]), int(roi_color[0]):int(roi_color[0]+roi_color[2])]


    img_r = np.zeros_like(img_bw)
    img_g = np.zeros_like(img_bw)
    img_b = np.zeros_like(img_bw)

    img_r = imCropped_color[..., 0]
    img_g = imCropped_color[..., 1]
    img_b = imCropped_color[..., 2]

    imCropped_color = np.float32(imCropped_color)/255.0
    img_bw = np.float32(img_bw)/255.0
    img_r = np.float32(img_r)/255.0
    img_g = np.float32(img_g)/255.0
    img_b = np.float32(img_b)/255.0

    img_bw = blur_edge(img_bw)
    img_r = blur_edge(img_r)
    img_g = blur_edge(img_g)
    img_b = blur_edge(img_b)

    IMG_BW = cv.dft(img_bw, flags=cv.DFT_COMPLEX_OUTPUT)
    IMG_R = cv.dft(img_r, flags=cv.DFT_COMPLEX_OUTPUT)
    IMG_G = cv.dft(img_g, flags=cv.DFT_COMPLEX_OUTPUT)
    IMG_B = cv.dft(img_b, flags=cv.DFT_COMPLEX_OUTPUT)


    defocus = '--circle' in opts

    def update(_):
        ang = np.deg2rad( cv.getTrackbarPos('angle', win) )
        d = cv.getTrackbarPos('d', win)
        noise = 10**(-0.1*cv.getTrackbarPos('SNR (db)', win))

        if defocus:
            psf = defocus_kernel(d)
        else:
            psf = motion_kernel(ang, d)
        cv.imshow('psf', psf)

        psf /= psf.sum()
        psf_pad = np.zeros_like(roi_bw)
        kh, kw = psf.shape
        psf_pad[:kh, :kw] = psf

        PSF = cv.dft(psf_pad, flags=cv.DFT_COMPLEX_OUTPUT, nonzeroRows = kh)
        PSF2 = (PSF**2).sum(-1)
        iPSF = PSF / (PSF2 + noise)[...,np.newaxis]

        RES_BW = cv.mulSpectrums(IMG_BW, iPSF, 0)
        # RES_R = cv.mulSpectrums(IMG_R, iPSF, 0)
        # RES_G = cv.mulSpectrums(IMG_G, iPSF, 0)
        # RES_B = cv.mulSpectrums(IMG_B, iPSF, 0)

        res_bw = cv.idft(RES_BW, flags=cv.DFT_SCALE | cv.DFT_REAL_OUTPUT )
        # res_r = cv.idft(RES_R, flags=cv.DFT_SCALE | cv.DFT_REAL_OUTPUT)
        # res_g = cv.idft(RES_G, flags=cv.DFT_SCALE | cv.DFT_REAL_OUTPUT)
        # res_b = cv.idft(RES_B, flags=cv.DFT_SCALE | cv.DFT_REAL_OUTPUT)

        # res_rgb = np.zeros_like(img_color)
        # res_rgb[..., 0] = res_r
        # res_rgb[..., 1] = res_g
        # res_rgb[..., 2] = res_b

        res_bw = np.roll(res_bw, -kh//2, 0)
        res_bw = np.roll(res_bw, -kw//2, 1)
        # res_rgb = np.roll(res_rgb, -kh // 2, 0)
        # res_rgb = np.roll(res_rgb, -kw // 2, 1)
        cv.imshow(win, res_bw)
        # cv.imshow(win, res_rgb)

    cv.namedWindow(win)
    cv.namedWindow('psf', 0)
    cv.createTrackbar('angle', win, int(opts.get('--angle', 135)), 180, update)
    cv.createTrackbar('d', win, int(opts.get('--d', 22)), 50, update)
    cv.createTrackbar('SNR (db)', win, int(opts.get('--snr', 25)), 50, update)
    update(None)

    while True:
        ch = cv.waitKey()
        if ch == 27:
            break
        if ch == ord(' '):
            defocus = not defocus
            update(None)

    print('Done')


if __name__ == '__main__':
    print(__doc__)
    main()
    cv.destroyAllWindows()
