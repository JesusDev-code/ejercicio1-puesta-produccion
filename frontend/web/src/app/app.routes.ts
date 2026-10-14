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
    path: 'registro',
    title: 'Crear cuenta · Incidentes',
    canActivate: [soloInvitados],
    loadComponent: () => import('./paginas/registro').then((m) => m.Registro),
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
