import { Routes } from '@angular/router';

import { requiereSesion, soloAdmin, soloInvitados } from './core/guardas';
import { Shell } from './ui/shell';

export const routes: Routes = [
  {
    path: 'login',
    title: 'Iniciar sesión · Incidentes',
    canActivate: [soloInvitados],
    loadComponent: () => import('./paginas/login').then((m) => m.Login),
  },
  {
    path: '',
    component: Shell,
    canActivate: [requiereSesion],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'incidentes' },
      {
        path: 'incidentes',
        title: 'Incidentes',
        loadComponent: () => import('./paginas/incidentes').then((m) => m.Incidentes),
      },
      {
        path: 'incidentes/nuevo',
        title: 'Nuevo incidente · Incidentes',
        loadComponent: () => import('./paginas/nuevo-incidente').then((m) => m.NuevoIncidente),
      },
      {
        path: 'incidentes/:id',
        title: 'Detalle · Incidentes',
        loadComponent: () => import('./paginas/detalle').then((m) => m.Detalle),
      },
      {
        path: 'usuarios',
        title: 'Usuarios · Incidentes',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/usuarios').then((m) => m.Usuarios),
      },
      {
        path: 'monitorizacion',
        title: 'Monitorización · Incidentes',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/monitorizacion').then((m) => m.Monitorizacion),
      },
      {
        path: 'eventos',
        title: 'Historial de eventos · Incidentes',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/eventos').then((m) => m.Eventos),
      },
      {
        path: 'auditoria',
        title: 'Auditoría · Incidentes',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/auditoria').then((m) => m.Auditoria),
      },
      {
        path: 'cuenta',
        title: 'Mi cuenta · Incidentes',
        loadComponent: () => import('./paginas/cuenta').then((m) => m.Cuenta),
      },
      {
        path: '**',
        title: 'No encontrado · Incidentes',
        loadComponent: () => import('./paginas/no-encontrado').then((m) => m.NoEncontrado),
      },
    ],
  },
];
