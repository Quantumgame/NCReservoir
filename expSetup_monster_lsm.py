'''
 Copyright (C) 2014 - Federico Corradi
 Copyright (C) 2014 - Juan Pablo Carbajal
 
 This progrm is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

############### author ##########
# federico corradi
# federico@ini.phys.ethz.ch
# Juan Pablo Carbajal 
# ajuanpi+dev@gmail.com
#
# ===============================
#!/usr/env/python
from __future__ import division

import numpy as np
from pylab import *
import pyNCS
import sys
import matplotlib
sys.path.append('../api/lsm/')
sys.path.append('../api/retina/')
sys.path.append('../gui/reservoir_display/')
import lsm as L
import time
from retina import Retina as ret

######################################
# Configure chip
try:
  is_configured
except NameError:
  print "Configuring chip"
  is_configured = False
else:
  print "Chip is configured: ", is_configured


if (is_configured == False):

    use_retina = True

    #populations divisible by 2 for encoders
    neuron_ids = np.linspace(0,255,256)
    npops      = len(neuron_ids)

    #setup
    prefix    = '../'
    setuptype = '../setupfiles/mc_final_mn256r1.xml'
    setupfile = '../setupfiles/final_mn256r1_retina_monster.xml'
    nsetup    = pyNCS.NeuroSetup(setuptype, setupfile, prefix=prefix)
    nsetup.mapper._init_fpga_mapper()

    chip      = nsetup.chips['mn256r1']

    chip.configurator._set_multiplexer(0)

    #populate neurons
    rcnpop = pyNCS.Population('neurons', 'for fun') 
    rcnpop.populate_by_id(nsetup,'mn256r1','excitatory', neuron_ids)

    if(not use_retina):
        chip.load_parameters('biases/biases_reservoir.biases')
    else:
        chip.load_parameters('biases/biases_reservoir_retina.biases')

    #init liquid state machine
    liquid = L.Lsm(rcnpop, cee=0.8, cii=0.5)

    #c = 0.2
    #dim = np.round(np.sqrt(len(liquid.rcn.synapses['virtual_exc'].addr)*c))

    if(use_retina):
        ###### configure retina
        inputpop = pyNCS.Population('','')
        inputpop.populate_by_id(nsetup,'mn256r1', 'excitatory', np.linspace(0,255,256))  
        #reset multiplexer
        chip.configurator._set_multiplexer(0)
        retina = ret(inputpop)
        retina._init_fpga_mapper()
        retmaps, pres, posts = retina.map_retina_to_mn256r1_macro_pixels()

        import RetinaInputs as ri
        win = ri.RetinaInputs(nsetup)
        #win.run(300)
    
    # do config only once
    is_configured = True
  
  
# End chip configuration
######################################

######################################
# Generate gestures parameters
num_gestures = 1 # Number of gestures
ntrials      = 1 # Number of repetitions of each gesture
nx_d = 16
ny_d = 16


gestures = []
for this_gesture in range(num_gestures):
    freqs   = (np.random.randint(3,size=3)+1).tolist()   # in Hz
    centers = (-1+2*np.random.random((3,2))).tolist()
    width   = (0.5+np.random.random(3)).tolist()
    gestures.append({'freq': freqs, 'centers': centers, 'width': width})
    
import json
json.dump(gestures, open("lsm/gestures.txt",'w'))
######################################

######################################
# Generate mean rate signals representing gestures
rates = [[]*len(gestures)]
G     = [[]*len(gestures)]
for ind,this_g in enumerate(gestures):
  for f  in this_g['freq']:
      rates[ind].append(lambda t,w=f: 0.5+0.5*np.sin(2*np.pi*w*t)) 

  # Multiple spatial distribution
  for width,pos in zip(this_g['width'], this_g['centers']):
      G[ind].append(lambda x,y,d=width,w=pos: np.exp ((-(x-w[0])**2 + (y-w[1])**2)/d**2))

# Number of time steps to sample the mean rates
nsteps = 50
######################################

# Function to calculate region of activity
func_avg = lambda t,ts: np.exp((-(t-ts)**2)/(2*150**2)) # time in ms

# Handle to figure to plot while learning
fig_h = figure()
fig_i = figure()
ion()

# Store scores of RC
scores = []
tot_scores_in = []
tot_scores_out = []
# Stimulation parameters
duration   = 1000   #ms
delay_sync = 500
framerate = 60
counts = (duration/1000)*framerate #for 60 frames per sec

# Time vector for analog signals
Fs    = 100/1e3 # Sampling frequency (in kHz)
T     = duration+delay_sync+1000
nT    = np.round (Fs*T)
timev = np.linspace(0,T,nT)

#Conversion from spikes to analog
membrane = lambda t,ts: np.atleast_2d(np.exp((-(t-ts)**2)/(2*30**2)))

liquid.RC_reset()
ac = []
syn_per_input_neu = 6
c = syn_per_input_neu/len(liquid.rcn.synapses['virtual_exc'].addr)
for ind,this_g in enumerate(gestures):

    M = liquid.create_stimuli_matrix(G[ind], rates[ind], nsteps, nx=nx_d ,ny=ny_d )
    #one stimiluation for  all trials --> NO VARIABILITY IN THE INPUTs
    stimulus = liquid.create_spiketrain_from_matrix(M, 
                                                    c = c, 
                                                    duration=duration,  
                                                    delay_sync=delay_sync,  
                                                    max_freq= 2800, min_freq = 400)
    
    #generate teaching signal associated with the Gesture
    teach_scale = arange(0.1,2,0.05)
    gesture_teach = rates[0][ind]((teach_scale*timev[:,None])*1e-3)
    #just poke it for the first time... to start in same configuration all the times..
    inputs, outputs = liquid.RC_poke(stimulus)
    
    for this_t in xrange(ntrials): 
    
        #stimulus = liquid.create_spiketrain_from_matrix(M, 
        #                                            c = c, 
        #                                            duration=duration,  
        #                                            delay_sync=delay_sync,  
        #                                            max_freq= 2800, min_freq = 400)
    
    
        #nsetup.chips['mn256r1'].load_parameters('biases/biases_reservoir.biases')
        #time.sleep(0.2)    
        #stimulate
        if not use_retina:
            inputs, outputs = liquid.RC_poke(stimulus)
        else:
            inputs, outputs = win.run(counts, framerate=framerate)

        # Convert input and output spikes to analog signals
        X = L.ts2sig(timev, membrane, inputs[0][:,0], np.floor(inputs[0][:,1]))
        Y = L.ts2sig(timev, membrane, outputs[0][:,0], outputs[0][:,1])
        
        #if(learn_real_time == True):
        # Calculate activity of current inputs.
        # As of now the reservoir can only give answers during activity
        tmp_ac = np.mean(func_avg(timev[:,None], outputs[0][:,0][None,:]), axis=1) 
        tmp_ac = tmp_ac / np.max(tmp_ac)
        if (np.sum(tmp_ac) > np.sum(ac)) or (this_t==0):   
            ac = tmp_ac[:,None]

        #teach_sig = L.orth_signal(X)*ac.T**4 #
        #teach_sig = L.orth_signal(X)[None,:]
        teach_sig = gesture_teach * ac**4 # Windowed by activity

        #learn
        liquid._realtime_learn (X,Y,teach_sig)
        print np.sum(liquid.CovMatrix['input']), np.sum(liquid.CovMatrix['output'])
        #evaluate
        zh = liquid.RC_predict (X,Y)
        score_in = liquid.RC_score(zh["input"], teach_sig)
        score_out = liquid.RC_score(zh["output"], teach_sig)
        
        tot_scores_in.append(score_in)
        tot_scores_out.append(score_out)
        #print "we are scoring...", scores
                
        #this_score = [liquid._regressor["input"].score(X,teach_sig)], \
        #             liquid._regressor["output"].score(Y,teach_sig)]
   
        #print this_score
        #print "we are plotting outputs"
        figure(fig_h.number)
        for i in range(256):
            subplot(16,16,i)
            plot(Y[:,i])
            axis('off')
        print "we are plotting inputs"
        figure(fig_i.number)
        for i in range(256):
            subplot(16,16,i)
            plot(X[:,i])
            axis('off')

         
#we plot the pearson correlation coeff
figure()            
for i in range(ntrials):
    plot(tot_scores_out[i][:,0], 'bo-')
    plot(tot_scores_in[i][:,0], 'ro-')


#predict
tot_in_scores = np.zeros([np.shape(teach_sig)[1], 2])
tot_out_scores = np.zeros([np.shape(teach_sig)[1], 2])
#for i in range(5):
inputs, outputs = liquid.RC_poke(stimulus)
# Convert input and output spikes to analog signals
X = L.ts2sig(timev, membrane, inputs[0][:,0], np.floor(inputs[0][:,1]))
Y = L.ts2sig(timev, membrane, outputs[0][:,0], outputs[0][:,1])
zh = liquid.RC_predict (X,Y)
pred_in_scores = liquid.RC_score(zh["input"], teach_sig)
pred_out_scores = liquid.RC_score(zh["output"], teach_sig)


figure()
plot(teach_scale, pred_in_scores [:,0], 'bo-', label="input")
xlabel("scale [au]")
ylabel("pearson corr coeff")
title(" performances")
legend(loc="best")


figure()
plot(teach_scale, pred_out_scores[:,0], 'ro-', label="output")
xlabel("scale [au]")
ylabel("pearson corr coeff")
title(" performances")
legend(loc="best")


figure()
zh = liquid.RC_predict (X,Y)
clf()
for i in range(len(teach_scale)):
    subplot(7,7,i+1)
    plot(timev,teach_sig[:,i],label='teach signal')
    plot(timev,zh["input"][:,i], label='input')
    plot(timev,zh["output"][:,i], label='output')
legend(loc='best')

#check non linearity
#figure()
#a,b = np.where(X>0)
#plot(X[:,b[0]], Y, 'o')
#figure()
#a,b = np.where(X>0)
#plot(X[:,b[1]], Y, 'o')
