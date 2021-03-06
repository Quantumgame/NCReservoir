## Copyright (C) 2014 - Juan Pablo Carbajal
##
## This progrm is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program. If not, see <http://www.gnu.org/licenses/>.

## Author: Juan Pablo Carbajal <ajuanpi+dev@gmail.com>

## -*- texinfo -*-
## @deftypefn {Function File} {[@var{P} @var{A}] =} ts2sig (@var{t},@var{ts},@var{id},@var{v},@var{G},@var{dim})
## Converts spikes to continuous singals
## Build continuous signals from spikes at timestamps ts 
## generated by a 2D array of sensors. The signal is built 
## as y(x,y,t) = G(x,y) * sum over ts v(t,ts).
## Where G:[-1,1]x[-1,1] --> [0,1] is a spatial gain and
## v: [0,T]x[0,T] --> [-1,1] is the temporal basis.
## @end deftypefn

function [P A] = ts2sig (t,ts,id,v,G,dim)
  nx = dim(1);
  ny = dim(2);
  N = nx*ny;

  nT  = length (t);
  nid = unique (id);
  nS  = length (nid);
  if nT*nS/N < 0.5
    P = sparse (zeros (nT,N));
  else
    P = zeros (nT,N);
  endif
  A = zeros (nT,N);

  # If G is time independent is useless.
  [x,y] = id2xy (nid,dim);
  g     = G(x.',y.',t);

  for i = 1:nS
    k  = find(id==nid(i));
    ii = double(nid(i))+1;
    P(:,ii) = sum (v(t,ts(k).'),2);
    A(:,ii) = g(:,i);
  endfor

endfunction

