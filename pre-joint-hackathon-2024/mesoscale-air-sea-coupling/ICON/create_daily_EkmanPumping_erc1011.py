#!/usr/bin/env python
# coding: utf-8

# 
# Compute mesoscale eddy-induced Ekman pumping (tau curl and vorticity gradient) 
#
import sys
yr=sys.argv[1]
mth=sys.argv[2]
yyyy=int(yr)

import glob, os
from subprocess import call
import multiprocessing
from netCDF4 import Dataset
import netCDF4 as nc
import xarray as xr
import numpy as np
import datetime

sys.path.insert(0, r'/home/m/m300466/pyfuncs')
from extractICONdata import *
from edgevertexcell import *

sys.path.append('/work/mh0256/m300466/pyicon')
import pyicon as pyic


run='erc1011'
gname = 'r2b9_oce_r0004'
lev = 'L128'
rgrid_name = 'global_0.05'
path_data     = f'/work/bm1344/k203123/experiments/{run}/'
path_grid     = f'/work/mh0256/m300466/icongrids/grids/{gname}/'
path_ckdtree  = f'{path_grid}ckdtree/'
fpath_ckdtree = f'{path_grid}ckdtree/rectgrids/{gname}_res0.05_180W-180E_90S-90N.npz'
#fpath_fx      = f'{path_grid}{gname}_{lev}_fx.nc'
#fpath_tgrid=f'{path_grid}{gname}_tgrid.nc'
fpath_tgrid=f'/pool/data/ICON/grids/public/mpim/0016/icon_grid_0016_R02B09_O.nc'
print(fpath_tgrid)
#exit(1)

f = Dataset(fpath_tgrid, 'r')
clon = f.variables['clon'][:] * 180./np.pi
clat = f.variables['clat'][:] * 180./np.pi
f.close()

#Fakely use atm model type to substitute for 2D ocean only [runs much faster!!!]
IcDo = pyic.IconData(
    fname        = run+'_oce_2d_1d_mean_20020101T000000Z.nc',
    path_data    = path_data+'run_20020101T000000-20020131T235845/',
    path_grid    = path_grid,
    gname        = gname,
    lev          = lev,
    rgrid_name   = rgrid_name,
    #load_rectangular_grid = False,
    do_triangulation    = False,
    omit_last_file      = False,
    load_vertical_grid = False,
    #calc_coeff          = True,
    #calc_coeff_mappings = False,
    model_type = 'atm',
              )

fpath_ckdtree = IcDo.rgrid_fpath_dict[rgrid_name]
IcDo.fixed_vol_norm = pyic.calc_fixed_volume_norm(IcDo)
IcDo.edge2cell_coeff_cc = pyic.calc_edge2cell_coeff_cc(IcDo)
IcDo.edge2cell_coeff_cc_t = pyic.calc_edge2cell_coeff_cc_t(IcDo)

expid='erc1011'
outdir='/work/mh0287/m300466/EERIE/'+expid+'/Ekman/'
#ds2d = xr.open_mfdataset(path_data+'run_200[2-8]*/'+expid+'_oce_2d_1d_mean_'+'*T000000Z.nc')
#ds2d = xr.open_mfdataset(path_data+'run_'+str(yyyy)+'*/'+expid+'_oce_2d_1d_mean_'+'*T000000Z.nc')
if float(mth)<10:
    mm='0'+str(int(mth))
else:
    mm=str(int(mth))
ds2d = xr.open_mfdataset(path_data+'run_'+str(yyyy)+mm+'*/'+expid+'_oce_2d_1d_mean_'+'*T000000Z.nc')
#ds3d = xr.open_mfdataset(path_data+'run_200[2-8]*/'+expid+'_oce_ml_1d_mean_'+'*T000000Z.nc')

#Need vorticity grid
dso = xr.open_dataset('/work/mh0287/m300083/experiments/dpp0066/dpp0066_oce_3dlev_P1D_20200909T000000Z.nc')

gridds=xr.open_dataset(fpath_tgrid)
#Coriolis
omega=7.2921159e-5 #radians/second
fCo=2*omega*np.sin(gridds.clat.values)
Colatlim=2 #Coriolis latitude limit
g0=9.81 #gravity 
rho0=1024 #density ref

import numpy.ma as ma
fillval=np.nan
dsmask=gridds['cell_sea_land_mask']
lsmask2=ma.masked_values(np.where(dsmask.values!=-2,fillval,1),fillval)
lsmask=ma.masked_values(np.where(dsmask.values>=0,fillval,1),fillval)

#For daily data:
fdatearrf=ds2d.time.dt.strftime("%Y%m%d.%f")
fdatearr=ds2d.time.dt.strftime("%Y%m%d")
#Need to shift by 12 hours to get the right date
newdatearrflist=[]
newdatearrlist=[]
for tt in range(len(ds2d.time.data)):
    # newdatelist.append(datetime.datetime.strptime(str(ds2d.time.data[tt])[:10], '%Y-%m-%d')-datetime.timedelta(hours=12))
    newdatearrflist.append((datetime.datetime.strptime(str(ds2d.time.data[tt])[:10], '%Y-%m-%d')-datetime.timedelta(hours=12)).strftime("%Y%m%d.%f"))
    newdatearrlist.append((datetime.datetime.strptime(str(ds2d.time.data[tt])[:10], '%Y-%m-%d')-datetime.timedelta(hours=12)).strftime("%Y%m%d"))
newdatearrf=np.array(newdatearrflist)
newdatearr=np.array(newdatearrlist)

#for ii in range(0,1):
#for ii in range(0,np.shape(fdatearr)[0]):
for ii in range(0,len(fdatearr)):
    #fdate=str(fdatearr[ii].values)
    fdate=newdatearr[ii]
    print('Processing for '+fdate)

    print('Extracting TAUX')
    tauu=ds2d['atmos_fluxes_stress_xw'].sel(time=fdatearr[ii]).values.squeeze()
    #print('size of taux=',np.shape(tauu))
    print('Extracting TAUY')
    tauv=ds2d['atmos_fluxes_stress_yw'].sel(time=fdatearr[ii]).values.squeeze()
    #print('size of tauy=',np.shape(tauv))

    #Compute angle of windstress to mask noisy data from curls
    mtau=np.sqrt(tauu*tauu + tauv*tauv)
    cosphi=tauu/mtau
    sinphi=tauv/mtau
    print('taumag=',np.shape(mtau))
    print('cosphi=',np.shape(cosphi))
    print('sinphi=',np.shape(sinphi))
    del(mtau)
    
    # Wind stress curl
    print('Project fluxes on 3D sphere')
    p_tau = pyic.calc_3d_from_2dlocal(IcDo, tauu[np.newaxis,:], tauv[np.newaxis,:])
    print('p_tau=',np.shape(p_tau))
    # del(tauu)
    # del(tauv)

    # calculate edge array
    print('Project from cell centre to edges')
    ptp_tau = pyic.cell2edges(IcDo, p_tau.squeeze())
    print('ptp_tau=',np.shape(ptp_tau))
    del(p_tau)
    
    print('rot_coeff=',np.shape(IcDo.rot_coeff))
    print('edges_of_vertex=',np.shape(IcDo.edges_of_vertex))
    print('Compute curl of wind stress (single level)')
    ptv_curl_tau = (ptp_tau[np.newaxis,IcDo.edges_of_vertex]*IcDo.rot_coeff[np.newaxis,:,:]).sum(axis=2)
    print('curl_tau=',np.shape(ptv_curl_tau))
    del(ptp_tau)
    print('Convert to xarray')
    ptv_curl_tau=xr.DataArray(ptv_curl_tau.squeeze(), coords=dict(ncells_3=(["ncells_3"],dso.ncells_2.data)) , dims=["ncells_3"])
    print('Project from vertices to cell centre')
    curl_tau=vertex2cell(ptv_curl_tau,IcDo)
    print('curl_tau=',np.shape(curl_tau))
    curl_tau=np.where(np.isnan(cosphi),fillval,curl_tau)
    curltau=np.where(np.abs(curl_tau)>=2e-5,fillval,curl_tau)*lsmask2
    del(curl_tau)
    del(ptv_curl_tau)
    del(cosphi)
    del(sinphi)
    
    print('Extracting SSH')
    ssh=ds2d['ssh'].sel(time=fdatearr[ii]).values.squeeze()
    print('size of ssh=',np.shape(ssh))

    # print('Extracting SST')
    # ts=ds2d['to'].isel(depth=0).sel(time=fdatearr[ii]).values.squeeze()
    # print('size of ts=',np.shape(ts))
    
    #Compute SSH gradients
    print('Compute gradient (located on edge)')
    print(np.shape(IcDo.adjacent_cell_of_edge))
    gradh_ssh = (ssh[np.newaxis,IcDo.adjacent_cell_of_edge[:,1]]-ssh[np.newaxis,IcDo.adjacent_cell_of_edge[:,0]])*IcDo.grad_coeff
    print('gradh_ssh=',np.shape(gradh_ssh))
    del(ssh)

    print('Project gradient onto cell centers (single level)')
    p_gradh_ssh = edges2cell(IcDo, gradh_ssh)
    print('p_gradhssh=',np.shape(p_gradh_ssh))
    del(gradh_ssh)

    print('Get d/dx and d/dy')
    dSSHdx, dSSHdy = pyic.calc_2dlocal_from_3d(IcDo, p_gradh_ssh)
    print('dSSHdx=',np.shape(dSSHdx))
    print('dSSHdy=',np.shape(dSSHdy))
    del(p_gradh_ssh)
    
    #Compute geostrophic surface velocity and remove noisy data
    ugeo=np.where(np.abs(g0*fCo)<=2*omega*np.sin(Colatlim/180*np.pi),fillval,(-g0/fCo)*dSSHdy)*lsmask2
    vgeo=np.where(np.abs(g0*fCo)<=2*omega*np.sin(Colatlim/180*np.pi),fillval,(g0/fCo)*dSSHdx)*lsmask2
    ugeo = ma.masked_values(ugeo,fillval)
    vgeo = ma.masked_values(vgeo,fillval)
    print('ugeo,vgeo = ',np.shape(ugeo))
    del(dSSHdy)
    del(dSSHdx)
        
    # Relative vorticity (curl)
    print('Project vectors on 3D sphere')
    p_geo = pyic.calc_3d_from_2dlocal(IcDo, ugeo, vgeo)
    print('p_geo=',np.shape(p_geo))
    del(ugeo)
    del(vgeo)

    # calculate edge array
    print('Project from cell centre to edges')
    ptp_geo = pyic.cell2edges(IcDo, p_geo.squeeze())
    print('ptp_geo=',np.shape(ptp_geo))
    del(p_geo)
    
    # calculate relative vorticity
    print('rot_coeff=',np.shape(IcDo.rot_coeff))
    print('edges_of_vertex=',np.shape(IcDo.edges_of_vertex))
    print('Compute relative vorticity of surface geostrophic current (single level)')
    ptv_vort = (ptp_geo[np.newaxis,IcDo.edges_of_vertex]*IcDo.rot_coeff[np.newaxis,:,:]).sum(axis=2)
    print('relative vorticity=',np.shape(ptv_vort))
    del(ptp_geo)
    print('Convert to xarray')
    ptv_vort=xr.DataArray(ptv_vort.squeeze(), coords=dict(ncells_3=(["ncells_3"],dso.ncells_2.data)) , dims=["ncells_3"])
    print('Project from vertices to cell centre')
    relvort=vertex2cell(ptv_vort,IcDo)*lsmask2
    print('relvort=',np.shape(relvort))
    del(ptv_vort)
    #Denoise
    nrelvort=np.where(np.abs(relvort)>=4e-5,fillval,relvort)
    nrelvort=np.where(np.abs(g0*fCo)<=2*omega*np.sin(Colatlim/180*np.pi),fillval,nrelvort)
    nrelvort = ma.masked_values(nrelvort,fillval)*lsmask2
    del(relvort)
    
    #Compute relative vorticity gradients
    print('Compute gradient (located on edge)')
    print(np.shape(IcDo.adjacent_cell_of_edge))
    gradh_relvort = (nrelvort[np.newaxis,IcDo.adjacent_cell_of_edge[:,1]]-nrelvort[np.newaxis,IcDo.adjacent_cell_of_edge[:,0]])*IcDo.grad_coeff
    print('gradh_ssh=',np.shape(gradh_relvort))
    # del(relvort)

    print('Project gradient onto cell centers (single level)')
    p_gradh_relvort = edges2cell(IcDo, gradh_relvort)
    print('p_gradhrelvort=',np.shape(p_gradh_relvort))
    del(gradh_relvort)

    print('Get d/dx and d/dy')
    dZdx, dZdy = pyic.calc_2dlocal_from_3d(IcDo, p_gradh_relvort)
    print('dZdx=',np.shape(dZdx))
    print('dZdy=',np.shape(dZdy))
    del(p_gradh_relvort)

    # Total Ekman upwelling by Stern [Curl of (tau/(f+zeta))]
    print('Project vectors on 3D sphere')
    p_Eks = pyic.calc_3d_from_2dlocal(IcDo, tauu/(fCo+nrelvort), tauv/(fCo+nrelvort))
    print('p_Eks=',np.shape(p_Eks))

    # calculate edge array
    print('Project from cell centre to edges')
    ptp_Eks = pyic.cell2edges(IcDo, p_Eks.squeeze())
    print('ptp_Eks=',np.shape(ptp_Eks))
    del(p_Eks)
    
    # calculate total Ekman upwelling (Stern)
    print('rot_coeff=',np.shape(IcDo.rot_coeff))
    print('edges_of_vertex=',np.shape(IcDo.edges_of_vertex))
    print('Compute total Ekman upwelling by Stern (single level)')
    ptv_Eks = (ptp_Eks[np.newaxis,IcDo.edges_of_vertex]*IcDo.rot_coeff[np.newaxis,:,:]).sum(axis=2)
    print('total Ekman upwelling (Stern) =',np.shape(ptv_Eks))
    del(ptp_Eks)
    print('Convert to xarray')
    ptv_Eks=xr.DataArray(ptv_Eks.squeeze(), coords=dict(ncells_3=(["ncells_3"],dso.ncells_2.data)) , dims=["ncells_3"])
    print('Project from vertices to cell centre')
    totEks=vertex2cell(ptv_Eks,IcDo)*lsmask2
    print('Eks=',np.shape(totEks))
    del(ptv_Eks)   
  
    #Compute Ekman pumping due to windstress curl and vorticity gradient
    print('Compute Ekman pumping due to windstress curl and vorticity gradient')
    Ek_curl=curltau/(rho0*(fCo+nrelvort))
    Ek_vortgrad=(tauu*dZdy.squeeze() - tauv*dZdx.squeeze())*lsmask2 /(rho0*np.square(fCo+nrelvort)) 
    Ek_Stern=totEks/rho0
    Ek_Classic=curltau/(rho0*fCo)
    print('Ekman curl=',np.shape(Ek_curl))
    print('Ekman vorticity gradient=',np.shape(Ek_vortgrad))
    print('Ekman Stern=',np.shape(Ek_Stern))
    print('Ekman Classic=',np.shape(Ek_Classic))        
    
    del(tauu)
    del(tauv)
    del(curltau)
    del(nrelvort)
    del(dZdx)
    del(dZdy)
    
    nctime = float(newdatearrf[ii])

#    wekcfile=outdir+'Wekcurl/dm/'+expid+'_Wekcurl_dm_'+fdate+'.nc'
#    print('Write to '+wekcfile)
#    writenc1d_r2b9O(wekcfile,nctime,14886338,Ek_curl,'Wekcurl','Ekman pumping induced by wind stress curl','Ekman_curl','m/s')
#
#    wekvfile=outdir+'Wekvortgrad/dm/'+expid+'_Wekvortgrad_dm_'+fdate+'.nc'
#    print('Write to '+wekvfile)
#    writenc1d_r2b9O(wekvfile,nctime,14886338,Ek_vortgrad,'Wekvortgrad','Ekman pumping induced by vorticity gradient','Ekman_vortgrad','m/s')

    weksfile=outdir+'Wekstern/dm/'+expid+'_Wekstern_dm_'+fdate+'.nc'
    print('Write to '+weksfile)
    writenc1d_r2b9O(weksfile,nctime,14886338,Ek_Stern,'Wekstern','total Ekman pumping (Stern)','Ekman_Stern','m/s')

    wektfile=outdir+'Wekclassic/dm/'+expid+'_Wekclassic_dm_'+fdate+'.nc'
    print('Write to '+wektfile)
    writenc1d_r2b9O(wektfile,nctime,14886338,Ek_Classic,'Wekclassic','Ekman pumping (Classic)','Ekman_Classic','m/s')    
    
    del(Ek_curl)
    del(Ek_vortgrad)
    del(Ek_Stern)
    del(Ek_Classic)

    
