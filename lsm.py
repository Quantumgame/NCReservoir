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
# Liquid State Machine class mn256r1 
# ===============================

### ========================= import packages ===============================
import random
import numpy as np
import time
import pyNCS
import matplotlib
from pylab import *
from sklearn.linear_model import Ridge
from sklearn import metrics

class Lsm:
    def __init__(self, population,  cee=0.5, cii=0.3, use_chip = False):
        ### ========================= define what is needed to program the chip ====
        # resources
        self.matrix_learning_rec = np.zeros([256,256])
        self.matrix_learning_pot = np.zeros([256,256])
        self.matrix_programmable_rec = np.zeros([256,256])
        self.matrix_programmable_w = np.zeros([256,256])
        self.matrix_programmable_exc_inh = np.zeros([256,256])
        # end resources
        # network parameters
        self.cee = cee
        self.cii = cii
        self.rcn = population
        self.setup = population.setup
        # init reservoir 
        if(use_chip == True):
            self.setup.chips['mn256r1'].load_parameters('biases/biases_default.biases')
            self._init_lsm()
            self.program_config()
            self.setup.chips['mn256r1'].load_parameters('biases/biases_reservoir.biases')

    ### ========================= functions ===================================
    def _init_lsm(self):
        # rcn with learning synapses
        self._connect_populations_programmable(self.rcn,self.rcn,self.cee,[2])
        self._connect_populations_programmable_inh(self.rcn,self.rcn,self.cii,[2])
        return 

    def _connect_populations_programmable_inh(self, pop_pre,pop_post,connectivity,w):
        '''
            Connect two populations via programmable synapses with specified connectivity and w
        '''    
        if(np.shape(w)[0] == 2):
            w_min = w[0]        
            w_max = w[1]
            random_w = True
        elif(np.shape(w)[0] == 1 ):
            random_w = False
        else:
            print 'w should be np.shape(2), [w_min,w_max]'

        #loop trought the pop and connect with probability connectivity
        for pre in pop_pre.soma.addr['neu']:
            for post in pop_post.soma.addr['neu']:
                coin = np.random.rand()
                if(coin < connectivity):
                    #we connect this pre with this post
                    self.matrix_programmable_exc_inh[post,pre] = 0  
                    self.matrix_programmable_rec[post,pre] = 1    
                    if(random_w):
                        self.matrix_programmable_w[post,pre] = np.random.randint(w_max)+w_min
                    else:
                        self.matrix_programmable_w[post,pre] = w[0]

    def _connect_populations_learning(self, pop_pre,pop_post,connectivity,pot):
        '''
            Connect two populations via learning synapses with specified connectivity and pot
        '''    
        #loop trought the pop and connect with probability connectivity
        for pre in pop_pre.soma.addr['neu']:
            for post in pop_post.soma.addr['neu']:
                coin = np.random.rand()
                if(coin < connectivity):
                    #we connect this pre with this post
                    self.matrix_learning_rec[post,pre] = 1 
                    coin = np.random.rand()
                if(coin < pot):  
                    self.matrix_learning_pot[post,pre] = 1

    def _connect_populations_programmable(self, pop_pre, pop_post,connectivity,w):
        '''
            Connect two populations via programmable synapses with specified connectivity and w
        '''    
        if(np.shape(w)[0] == 2):
            w_min = w[0]        
            w_max = w[1]
            random_w = True
        elif(np.shape(w)[0] == 1 ):
            random_w = False
        else:
            print 'w should be np.shape(2), [w_min,w_max]'

        #loop trought the pop and connect with probability connectivity
        for pre in pop_pre.soma.addr['neu']:
            for post in pop_post.soma.addr['neu']:
                coin = np.random.rand()
                if(coin < connectivity):
                    #we connect this pre with this post
                    self.matrix_programmable_exc_inh[post,pre] = 1
                    self.matrix_programmable_rec[post,pre] = 1   
                    if(random_w):
                        self.matrix_programmable_w[post,pre] = np.random.randint(w_max)+w_min
                    else:
                        self.matrix_programmable_w[post,pre] = w[0]

    def _generate_input_mean_rates (self,G, rates, nT, nx=16, ny=16) :
        '''
        Generates a matrix the mean rates of the input neurons defined in
        nT time intervals.
        
        ** Inputs **
        G: A list with G_i(x,y), each element is a function 
                G_i: [-1,1]x[-1,1] --> [0,1] 
           defining the intensity of mean rates on the (-1,1)-square.
        nx,ny: Number of neurons in the x and y direction (default 16).

        rates: A list with the time variations of the input mean rates.
               Each element is
                f_i: [0,1] --> [0,1]
        
        nT: Number of time intervals.

        ** Outputs **
        '''
        
        nR = len(rates) # Number of rates
#        if not nR == len(G):
#            # TODO: Raise an error
#            print "Rates and G must have the same length."
#            return 
        
        # Square
        x,y = np.meshgrid(np.linspace(-1,1,nx), np.linspace(-1,1,ny))
        t   = np.linspace(0,1,nT,endpoint=False)
        V   = np.array([r(t) for r in rates])

        M = np.zeros ([nx*ny, nT])
        for g,r in zip(G,V):
            M += np.array(g(x,y).ravel()[:,None] * r) / sum (g(x,y).ravel()[:,None])

        return M

    def stimulate_reservoir(self, rate_matrix, max_freq = 1000, min_freq = 350, duration = 1000, trials=5, neu_sync = 10, delay_sync = 500, duration_sync = 200, freq_sync=200,plot_samples = False):
        '''
        stimulate reservoir via virtual input synapses
        nsteps -> time steps to be considered in a duration = duration
        max_freq -> max input freq
        min_freq -> min input freq
        trials -> number of different stimulations with inhonogeneous poisson spike trains
        rate_matrix -> normalized rate matrix with dimensions [nsyn,timebins]
        '''
        vsyn = 4
        somach = self.rcn.soma.channel
        inputch = 1
        M = rate_matrix
        nsyn, nsteps = np.shape(M)

        #we pick a random projection
        nsyn_tot = len(self.rcn.synapses['virtual_exc'].addr)
        index_syn_tot = np.linspace(0,nsyn_tot-1, nsyn_tot)
        np.random.shuffle(index_syn_tot)
        index_syn = index_syn_tot[0:nsyn]
        tot_outputs = []
        tot_inputs = []
        
        #stim_matrix = r_[[500*np.random.random(len(self.rcn.soma.addr)*vsyn)]*nsteps]
        #stim_matrix = r_[[np.linspace(min_freq,max_freq,len(self.rcn.soma.addr)*vsyn)]*nsteps]
        #stim_matrix = np.r_[[np.linspace(min_freq,max_freq,nsyn)]*nsteps]
        timebins = np.linspace(0, duration, nsteps)
        syn = self.rcn.synapses['virtual_exc'][index_syn.astype(int)]

        #rescale M to max/min freq
        new_value = np.ceil(( (M - np.min(M)) / (np.max(M) - np.min(M)) ) * (max_freq  - min_freq) + min_freq)

        index_neu = self.rcn.synapses['virtual_exc'].addr['neu'] == neu_sync           
        syn_sync = self.rcn.synapses['virtual_exc'][index_neu]
        sync_spikes = syn_sync.spiketrains_regular(freq_sync,duration=duration_sync)

        timev = np.linspace(0,duration+delay_sync+1000,2000)
        func_timebase = lambda t,ts: np.exp((-(t-ts)**2)/(2*50**2))
        
        #create mean rates basis
        if(plot_samples == True):
            figure()
        spiketrain = syn.spiketrains_inh_poisson(new_value,timebins+delay_sync)
        #spiketrain = syn.spiketrains_regular(min_freq*2, duration=duration+delay_sync)
        stimulus = pyNCS.pyST.merge_sequencers(sync_spikes, spiketrain)
        for this_stim in range(trials):
            out = self.setup.stimulate(stimulus, send_reset_event=False, duration=duration+delay_sync+1000)
            out = out[somach]
            #sync data with sync neuron
            raw_data = out.raw_data()
            sync_index = raw_data[:,1] == neu_sync
            start_time = np.min(raw_data[sync_index,0])
            index_after_sync = raw_data[:,0] > start_time
            clean_data = raw_data[index_after_sync,:]
            clean_data[:,0] = clean_data[:,0]-np.min(clean_data[:,0])
            #copy synched data
            tot_outputs.append(clean_data)
            tot_inputs.append(spiketrain[inputch].raw_data())
            if(plot_samples == True):
                Y = self._ts2sig(timev,tot_outputs[this_stim][:,0], tot_outputs[this_stim][:,1], func_timebase, 256 )
                for i in range(256):
                    subplot(16,16,i)
                    plot(Y[:,i])

        return tot_inputs, tot_outputs

    def plot_inout(self, inputs,outputs):
        '''
        just plot input and output trials of reservoir after stimulate reservoir
        '''
        trials = len(inputs)
        figure()
        for i in range(trials):
            plot(inputs[i][:,0],inputs[i][:,1],'o')
            xlabel('time [s]')
            ylabel('neuron id')
            title('input spike trains')
        for i in range(trials):
            figure()
            plot(outputs[i][:,0],outputs[i][:,1],'o')
            xlabel('time [s]')
            ylabel('neuron id')
            title('output spike trains')

    def load_config(self, directory='lsm/'):
        '''
            load configuration from folder 
        '''
        self.popsne = np.loadtxt(directory+'popse.txt')
        self.popsni = np.loadtxt(directory+'popsi.txt')
        self.matrix_learning_rec = np.loadtxt(directory+'conf_matrix_learning_rec.txt')
        self.matrix_learning_pot = np.loadtxt(directory+'conf_matrix_learning_pot.txt')
        self.matrix_programmable_rec = np.loadtxt(directory+'conf_matrix_programmable_rec.txt')
        self.matrix_programmable_w = np.loadtxt(directory+'conf_matrix_programmable_w.txt')
        self.matrix_programmable_exc_inh = np.loadtxt(directory+'conf_matrix_matrix_programmable_exc_inh.txt')

    def save_config(self, directory = 'lsm/'):
        '''
            save matrices configurations
        '''
        np.savetxt(directory+'conf_matrix_learning_rec.txt', self.matrix_learning_rec)
        np.savetxt(directory+'conf_matrix_learning_pot.txt', self.matrix_learning_pot)
        np.savetxt(directory+'conf_matrix_programmable_rec.txt', self.matrix_programmable_rec)
        np.savetxt(directory+'conf_matrix_programmable_w.txt', self.matrix_programmable_w)
        np.savetxt(directory+'conf_matrix_matrix_programmable_exc_inh.txt', self.matrix_programmable_exc_inh)

    def program_config(self):
        '''
        upload configuration matrices on the neuromorphic chip mn256r1
        '''
        self.setup.mapper._program_onchip_weight_matrix_programmable(self.matrix_programmable_w)
        self.setup.mapper._program_onchip_programmable_connections(self.matrix_programmable_rec)
        self.setup.mapper._program_onchip_exc_inh(self.matrix_programmable_exc_inh)
        self.setup.mapper._program_onchip_learning_state(self.matrix_learning_pot)
        self.setup.mapper._program_onchip_plastic_connections(self.matrix_learning_rec)
      
    def _ismember(self, a,b):
        '''
        as matlab: ismember
        '''
        # tf = np.in1d(a,b) # for newer versions of numpy
        tf = np.array([i in b for i in a])
        u = np.unique(a[tf])
        index = np.array([(np.where(b == i))[0][-1] if t else 0 for i,t in zip(a,tf)])
        return tf, index

    def mean_neu_firing(self, spike_train, n_neurons,nbins=10):
        '''
        return mean neu firing matrix
        '''
        simulation_time = [np.min(spike_train[:,0]),np.max(spike_train[:,0])]
        un, bins = np.histogram(simulation_time,nbins)
        mean_rate = np.zeros([len(n_neurons),nbins])
        for b in range(nbins-1):
            #simulation_time = [np.min(spike_train[0][:]), np.max(spike_train[0][:])]
            for i in range(len(n_neurons)):
                index_neu = np.where(np.logical_and(spike_train[:,1] == n_neurons[i], np.logical_and(spike_train[:,0] >     bins[b] , spike_train[:,0] < bins[b+1] )) )
                mean_rate[i,b] = len(index_neu[0])*1000.0/(bins[b+1]-bins[b]) # time unit: ms
        return mean_rate

    def poke_and_record(self, c=0.3, nsteps=30, num_gestures= 1, ntrials = 4, do_plot = False, learn_real_time = False):
        '''
        c -> random connectivity from stimuli to reservoir
        nsteps -> timesteps
        num_gestures -> stuff to classify generated
        ntrials -> number of trials per gesture
        '''
        dim = np.round(np.sqrt(len(self.rcn.synapses['virtual_exc'].addr)*c))
        gestures = []
        for this_gesture in range(num_gestures):
            freqs = np.random.randint(7,size=3).tolist()   
            centers = np.random.random((3,2)).tolist()
            width = np.random.random((1,3)).tolist()
            gestures.append([{'freq': freqs, 'centers': centers, 'width': width}])

        import json
        json.dump(gestures, open("lsm/gestures.txt",'w'))
        #gestures = [ {'freq':[1,5,7], 'centers': [(0.0,-0.5),(0.8,0.8),(-0.8,0.3)], 'width': [1.2,0.5,1.3]} ]
        rates = []

        timev = np.linspace(0,1550,1550)
        func_timebase = lambda t,ts: np.exp((-(t-ts)**2)/(2*50**2))
        values = np.linspace(-1,1,256)
        self.decoders = []

        for ind,this_g in enumerate(gestures):
            #fixed gesture g
            for f  in this_g[0]['freq']:
                rates.append(lambda t,w=f: 0.5+0.5*np.sin(2*np.pi*w*t))

            # Multiple spatial distribution
            G = []
            for width,pos in zip(this_g[0]['width'], this_g[0]['centers']):
                G.append(lambda x,y,d=width,w=pos: np.exp ((-(x-w[0])**2 + (y-w[1])**2)/(np.sum(width)**2)))

            M = self._generate_input_mean_rates(G, rates, nsteps, nx=dim, ny=dim) 

            inputs, outputs = self.stimulate_reservoir(M,trials=ntrials, plot_samples=True)
            if( do_plot == True):
                print "plotting..."
                ion()
                figure()    
                hold(True)

            #Linear least squares with l2 regularization.
            self.clf = Ridge(alpha=1.0)
                    
            for trial in range(ntrials):
                np.savetxt("lsm/inputs_gesture_"+str(ind)+"_trial_"+str(trial)+".txt", inputs[trial])
                np.savetxt("lsm/outputs_gesture_"+str(ind)+"_trial_"+str(trial)+".txt", outputs[trial])

                if(learn_real_time == True):
                    #pass output trought the membrane
                    X = self._ts2sig(timev,inputs[trial][:,0], np.floor(inputs[trial][:,1]), func_timebase , 256 )
                    Y = self._ts2sig(timev,outputs[trial][:,0], outputs[trial][:,1], func_timebase, 256 )
                    #learn transformation -1 1
                    if(trial < ntrials -1):
                        self.clf.fit(Y.T,values)
                    else:
                        print "we are trying to predict this one"
                        self.pred = self.clf.predict(Y.T)                        
                        self.score = 1 - metrics.f1_score(values, self.pred) 
                        print  "we scored: ", self.score

                if(do_plot ==True):
                    X = self._ts2sig(timev,inputs[trial][:,0], np.floor(inputs[trial][:,1]), func_timebase , 256 )
                    Y = self._ts2sig(timev,outputs[trial][:,0], outputs[trial][:,1], func_timebase, 256 )
                    ac=np.mean(Y**2,axis=0)
                    max_pos = np.where(ac == np.max(ac))[0]
                    subplot(3,1,1)
                    plot(X[:,125])
                    subplot(3,1,2)
                    plot(Y[:,max_pos])
                    subplot(3,1,3)
                    CO = np.dot(Y.T,Y)
                    CI = np.dot(X.T,X)
                    si = np.linalg.svd(CI, full_matrices=True, compute_uv=False)
                    so = np.linalg.svd(CO, full_matrices=True, compute_uv=False)
                    semilogy(so/so[0], 'bo-', label="outputs")
                    semilogy(si/si[0], 'go-', label="inputs")
                    legend(loc="best")
                    #try decoders
                    decoders = self.compute_decoders(values, Y)
                    self.decoders.append(decoders)
        return       

    ### HELPER FUNCTIONS
    def _ts2sig (self, t,ts,n_id,time_resp,N):
        '''
        lsm.ts2sig(np.linspace(0,1000,1000),outputs[:,0], outputs[:,1], lambda t,ts: np.exp((-(t-ts)**2)/(2*100)), 256 )
        '''
        nT = len(t)
        nid = np.unique(n_id)
        nS = len(nid)
        Y = np.zeros([nT,N])
        for i in xrange(nS):
            idx = np.where(n_id == nid[i])[0]
            for j in idx:
                # import pdb; pdb.set_trace()
                Y[:,i] += time_resp(t,ts[j]);
        return Y

    def compute_decoders(self, values, Y):
        '''
        solve decoders for inputs
        values has dim 256
        Y has dim nT,256
        '''
        gamma=np.dot(Y, Y.T) #I diagonal noise add I = eye(len(gamma))
        upsilon=np.dot(Y, values) #associated function 
        ginv=np.linalg.pinv(gamma)
        decoders=np.dot(ginv,upsilon)
        return decoders
