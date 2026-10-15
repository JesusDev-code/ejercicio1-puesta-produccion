import { inject } from '@angular/core';
import { Routes } from '@angular/router';

import {
  conEmpresa,
  requiereSesion,
  sinSesion,
  soloAdmin,
  soloGestor,
  soloInvitados,
  soloPendientes,
} from './core/guardas';
import { Sesion } from './core/sesion';
import { Shell } from './ui/shell';

export const routes: Routes = [
  {
    // Web pública de venta. Con sesión no casa y `/` sigue llevando a la consola
    path: '',
    pathMatch: 'full',
    title: 'Kaelum Security · Ciberseguridad gestionada',
    canMatch: [sinSesion],
    loadComponent: () => import('./paginas/inicio').then((m) => m.Inicio),
  },
  {
    path: 'login',
    title: 'Iniciar sesión · Kaelum Security',
    canActivate: [soloInvitados],
    loadComponent: () => import('./paginas/login').then((m) => m.Login),
  },
  {
    path: 'registro',
    title: 'Crear cuenta · Kaelum Security',
    canActivate: [soloInvitados],
    loadComponent: () => import('./paginas/registro').then((m) => m.Registro),
  },
  {
    // Fuera de la consola: una cuenta pendiente no tiene menú que ver
    path: 'unirse',
    title: 'Unirme a mi empresa · Kaelum Security',
    canActivate: [requiereSesion, soloPendientes],
    loadComponent: () => import('./paginas/unirse').then((m) => m.Unirse),
  },
  {
    path: '',
    component: Shell,
    canActivate: [requiereSesion, conEmpresa],
    children: [
      // El admin aterriza en el Panel; el resto, en sus incidencias
      {
        path: '',
        pathMatch: 'full',
        redirectTo: () => (inject(Sesion).esAdmin() ? 'monitorizacion' : 'incidentes'),
      },
      {
        path: 'incidentes',
        title: 'Incidencias · Kaelum Security',
        loadComponent: () => import('./paginas/incidentes').then((m) => m.Incidentes),
      },
      {
        path: 'incidentes/nuevo',
        title: 'Reportar incidencia · Kaelum Security',
        loadComponent: () => import('./paginas/nuevo-incidente').then((m) => m.NuevoIncidente),
      },
      {
        path: 'incidentes/:id',
        title: 'Incidencia · Kaelum Security',
        loadComponent: () => import('./paginas/detalle').then((m) => m.Detalle),
      },
      {
        path: 'mi-empresa',
        title: 'Mi empresa · Kaelum Security',
        canActivate: [soloGestor],
        loadComponent: () => import('./paginas/mi-empresa').then((m) => m.MiEmpresa),
      },
      {
        path: 'usuarios',
        title: 'Usuarios · Kaelum Security',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/usuarios').then((m) => m.Usuarios),
      },
      {
        path: 'monitorizacion',
        title: 'Panel · Kaelum Security',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/monitorizacion').then((m) => m.Monitorizacion),
      },
      {
        path: 'eventos',
        title: 'Eventos · Kaelum Security',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/eventos').then((m) => m.Eventos),
      },
      {
        path: 'sensores',
        title: 'Sensores · Kaelum Security',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/sensores').then((m) => m.Sensores),
      },
      {
        path: 'clientes',
        title: 'Clientes · Kaelum Security',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/clientes').then((m) => m.ClientesPagina),
      },
      {
        path: 'auditoria',
        title: 'Auditoría · Kaelum Security',
        canActivate: [soloAdmin],
        loadComponent: () => import('./paginas/auditoria').then((m) => m.Auditoria),
      },
      {
        path: 'cuenta',
        title: 'Mi cuenta · Kaelum Security',
        loadComponent: () => import('./paginas/cuenta').then((m) => m.Cuenta),
      },
      {
        path: '**',
        title: 'No encontrado · Kaelum Security',
        loadComponent: () => import('./paginas/no-encontrado').then((m) => m.NoEncontrado),
      },
    ],
  },
];
