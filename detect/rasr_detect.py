
"""
RASR Detect ver 3.0
as of Jan 09, 2021

See README for details

@authors: Benjamin Miller and Yash Sarda
"""

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=FutureWarning)
    warnings.simplefilter("ignore", category=DeprecationWarning)
    warnings.simplefilter("ignore", category=RuntimeWarning)

    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvas
    from matplotlib import pyplot as plt
    from matplotlib import patches

    import pyart

    import os

    import time

    import sys

    import numpy as np

    from multiprocessing import Pool, cpu_count, Lock, get_context
    from multiprocessing.pool import ThreadPool

    from functools import partial

    import gc

    from motion import org, kin, backprop
    from output import squareout, pointout, stringed, txtout
    from torchdet import detect

##############################################################################################################################


def readpyart(file, outdir, detdir, cint, vis): # Function to unpack the NOAA radar files, and evaluate them
    r, dr, allr = [], [], []

    file = file[len(fdir):]                           # (1)
    radar = pyart.io.read(fdir + file)
    name, date, btime, dtstr = stringed(file)
    print('\n')
    print('Checking ' + name + ' at ' + date)

    for x in range(radar.nsweeps):
        plotter = pyart.graph.RadarDisplay(radar)
        fig = plt.figure(figsize=(25, 25), frameon=False)
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        fig.add_axes(ax)
        plotter.set_limits(xlim=(-250, 250), ylim=(-250, 250), ax=ax)
        data = plotter._get_data('velocity', x, mask_tuple=None, filter_transitions=True, gatefilter=None)

        if np.any(data) > 0:
            xDat, yDat = plotter._get_x_y(x, edges=True, filter_transitions=True)
            data = data * (70 / np.max(np.abs(data)))
            ax.pcolormesh(xDat, yDat, data)
            canvas = FigureCanvas(fig)
            fig.canvas.draw()                                   # (1)
            img = np.array(canvas.renderer.buffer_rgba())       # This whole segment is converting the data to a standard size
            img = np.delete(img, 3, 2)                          # and readable image using matplotlib (MPL)


            sweepangle = str(format(radar.fixed_angle['data'][x], ".2f"))
            #print('Reading velocity at sweep angle: ', sweepangle)
            t = radar.time['data'][x]
            locDat = [xDat, yDat, t]
            v = detect(radar, img, file, locDat, sweepangle, detdir, vis, cint)    # detect is a function from torchdet.py
            if v is not None:
                vc, vall = v    # two types of output, for either point or square displays
                vc.append(x)
                r.append(vc)
                allr.append(vall)
            plt.cla()
            plt.clf()
            plt.close('all')
    if(len(r) >= 2):
        squareout(file, radar, allr, outdir)
        #pointout(file, radar, r, outdir)
        rlsp = org(r)
        rv = kin(rlsp)
        prop = backprop(rv,360)
        if (vis == True):
            propvis(prop, detdir, name, dtstr)
        txtout(prop, file, outdir)

def getListOfFiles(dirName):    # Converts a directory of files into an object iterable with pool (for parallelization)
    listOfFile = os.listdir(dirName)
    allFiles = list()
    for entry in listOfFile:
        fullPath = os.path.join(dirName, entry)
        if os.path.isdir(fullPath):
            allFiles = allFiles + getListOfFiles(fullPath)
        else:
            allFiles.append(fullPath)
    if len(allFiles) > 160:
        all_files = allFiles[:160]
    else:
        all_files = allFiles
    return all_files


def init(l):    # Honestly I still have no idea what this does
    global lock
    lock = l


###############################################################################################################################
# Relevant paths, confidence value, and visualization toggle:
fdir = 'data/'
outdir = 'falls/'
detdir = 'vis/'
cint = 0.85
vis = True     # Select True to print graphs and plots (good for debugging), and False to reduce file I/O.
               # False by default for the main function

try:
    for file in os.listdir(outdir):
        os.remove(outdir + file)
    for file in os.listdir(detdir):
        os.remove(detdir + file)
except FileNotFoundError:
    pass

if __name__ == '__main__':
    # optional spec for num pool workers, else num cpu
    if len(sys.argv) > 1:
        runnum = sys.argv[1]
    else:
        runnum = cpu_count() / 4
    try:
        all_files = getListOfFiles(fdir)
    except:
        all_files = []
        print('ERROR: path not found')
    top = len(all_files)
    if top != 0:
        l = Lock()
        n = int(runnum)
        partreadpyart = partial(readpyart, outdir=outdir, detdir=detdir, cint=cint, vis=vis)
        for i in range(0, top, n):
            print('Batch ' + str(int(i / n)) + ' of ' + str(int(top / n)) + ', initializing pool...')
            with get_context("spawn").Pool(processes=int(runnum), initializer=init, initargs=(l,)) as pool:
                print('   mapping...')
                for x in pool.imap(partreadpyart, all_files[i:i + n]):
                    # print(x)
                    gc.collect()  # clear each step
                #results = pool.map(getDataPart, all_files[i:i+n])
                time.sleep(1)  # should permit maxtasksperchild=1
                print('   closing batch...')
                pool.close()  # close chunk
                print('joining batch...')
                pool.join()  # join chunk to clean
            # pool.terminate() #terminate chunk
            print('   batch closed')
            gc.collect()  # clear at end
    else:
        print('ERROR: path not found')

#print ("Program took", time.time() - start_time, "to run")
