import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ROLES } from '../core/modelos';
import { Sesion } from '../core/sesion';
import { Glifos } from './glifos';
import { Marca } from './marca';

@Component({
  selector: 'app-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Glifos, Marca],
  template: `
    <div class="pagina contenedor">
      <app-glifos [densidad]="30" />

      <nav aria-label="Principal" class="menu">
        <app-marca class="marca" nombre="Kaelum" subtitulo="SECURITY · UMBRAL" [tam]="32" />

        <div class="grupo">
          <span class="cabecera-mono grupo-titulo">INCIDENCIAS</span>
          <a routerLink="/incidentes" routerLinkActive="activo" [routerLinkActiveOptions]="{ exact: true }" ariaCurrentWhenActive="page" class="item">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z" /></svg>
            Incidencias
          </a>
          <a routerLink="/incidentes/nuevo" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
            Reportar incidencia
          </a>
        </div>

        @if (sesion.esGestor()) {
          <div class="grupo">
            <span class="cabecera-mono grupo-titulo">MI EMPRESA</span>
            <a routerLink="/mi-empresa" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21V7l6-4v18M10 21h10V10l-10-3M14 13h2M14 17h2M6 11h1M6 15h1" /></svg>
              Equipo e invitaciones
            </a>
          </div>
        }

        @if (sesion.esAdmin()) {
          <div class="grupo">
            <span class="cabecera-mono grupo-titulo">CENTRO DE SEGURIDAD</span>
            <a routerLink="/monitorizacion" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l3 8 4-16 3 8h4" /></svg>
              Panel
            </a>
            <a routerLink="/eventos" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h10" /></svg>
              Eventos
            </a>
            <a routerLink="/sensores" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="2" /><path d="M8.5 8.5a5 5 0 000 7M15.5 8.5a5 5 0 010 7M5.6 5.6a9 9 0 000 12.8M18.4 5.6a9 9 0 010 12.8" /></svg>
              Sensores
            </a>
          </div>

          <div class="grupo">
            <span class="cabecera-mono grupo-titulo">ADMINISTRACIÓN</span>
            <a routerLink="/clientes" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21V7l6-4v18M10 21h10V10l-10-3M14 13h2M14 17h2M6 11h1M6 15h1" /></svg>
              Clientes
            </a>
            <a routerLink="/usuarios" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.5a3.5 3.5 0 010 7M18 14.8c2 .7 3.2 2.4 3.5 5.2" /></svg>
              Usuarios
            </a>
            <a routerLink="/auditoria" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M5 4h14v16H5zM9 9h6M9 13h6M9 17h3" /></svg>
              Auditoría
            </a>
          </div>
        }

        <div class="tarjeta-usuario">
          <a routerLink="/cuenta" class="usuario" title="Ir a Mi cuenta">
            <span aria-hidden="true" class="avatar">{{ inicial() }}</span>
            <span class="datos">
              <span class="email" [title]="sesion.usuario()?.email ?? ''">{{ sesion.usuario()?.email }}</span>
              <span class="rol">{{ rol() }}</span>
              @if (sesion.usuario()?.empresa_nombre; as empresa) {
                <span class="empresa" [title]="empresa">{{ empresa }}</span>
              }
            </span>
          </a>
          <a routerLink="/cuenta" routerLinkActive="activo" ariaCurrentWhenActive="page" class="item cuenta">
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4" /><path d="M4 21c1-4.2 4.2-6.5 8-6.5s7 2.3 8 6.5" /></svg>
            Mi cuenta
          </a>
          <button type="button" class="item salir" (click)="salir()">
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 4h3a2 2 0 012 2v12a2 2 0 01-2 2h-3M10 17l5-5-5-5M15 12H4" /></svg>
            Cerrar sesión
          </button>
        </div>
      </nav>

      <main class="principal">
        <router-outlet />
      </main>
    </div>
  `,
  styles: `
    /* overflow: clip y no hidden: hidden convierte el contenedor en caja de scroll y anula el sticky */
    .contenedor { display: flex; align-items: flex-start; overflow: clip; }
    .menu {
      position: sticky; top: 16px; z-index: 2; flex: 0 0 264px; height: calc(100vh - 32px); overflow-y: auto;
      margin: 16px 0 16px 16px; padding: 24px 16px; border-radius: 22px;
      display: flex; flex-direction: column; gap: 26px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.02));
      backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }
    .marca { padding: 0 8px; }
    .grupo { display: flex; flex-direction: column; gap: 4px; }
    .grupo-titulo { padding: 0 12px 8px; }
    .item {
      min-height: 46px; display: flex; align-items: center; gap: 12px; padding: 0 14px; border: 0; border-radius: 14px;
      background: transparent; color: var(--texto-2); text-decoration: none; font-family: inherit; font-size: 14px;
      font-weight: 500; cursor: pointer; transition: background 0.2s;
    }
    .item:hover { background: rgba(255, 255, 255, 0.05); color: var(--texto); }
    .item.activo {
      background: linear-gradient(90deg, rgba(224, 30, 60, 0.28), rgba(224, 30, 60, 0.06));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 0 24px -6px rgba(224, 30, 60, 0.5);
      color: #fff4f1; font-weight: 600;
    }
    .tarjeta-usuario {
      margin-top: auto; display: flex; flex-direction: column; gap: 14px; padding: 16px; border-radius: 16px;
      background: rgba(0, 0, 0, 0.28);
    }
    .usuario { display: flex; align-items: center; gap: 12px; color: var(--texto); text-decoration: none; border-radius: 12px; }
    .usuario:hover .email { color: var(--oro-claro); }
    .avatar {
      width: 36px; height: 36px; flex: none; border-radius: 50%; display: flex; align-items: center; justify-content: center;
      background: linear-gradient(140deg, #d4af6e, #7a5a26); color: #1a1008; font-weight: 700; font-size: 14px;
    }
    .datos { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .email {
      font-size: 13px; font-weight: 600; transition: color 0.2s;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .rol { font-family: var(--mono); font-size: 10px; letter-spacing: 2px; color: var(--oro); }
    .empresa {
      font-size: 12px; color: var(--apagado);
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .salir, .cuenta { justify-content: center; background: rgba(255, 255, 255, 0.04); font-size: 13px; font-weight: 600; min-height: 44px; }
    .tarjeta-usuario .item + .item { margin-top: -6px; }
    .principal {
      position: relative; flex: 1 1 auto; min-width: 0; padding: 40px 48px 56px;
    }

    /* Pantallas bajas (portátil a 768 px de alto): el menú se compacta para que quepa entero */
    @media (max-height: 820px) and (min-width: 901px) {
      .menu { gap: 16px; padding: 18px 14px; }
      .grupo-titulo { padding-bottom: 4px; }
      .item { min-height: 40px; }
      .tarjeta-usuario { gap: 10px; padding: 12px; }
    }

    /* Tablet y móvil: barra compacta arriba, enlaces en fila */
    @media (max-width: 900px) {
      .contenedor { flex-direction: column; align-items: stretch; }
      .menu {
        position: relative; top: 0; flex: none; height: auto; overflow: visible;
        margin: 12px 12px 0; padding: 14px; gap: 12px;
        flex-direction: row; flex-wrap: wrap; align-items: center;
      }
      .marca { flex: 1 1 100%; padding: 0 4px 4px; }
      .grupo { flex-direction: row; flex-wrap: wrap; gap: 6px; }
      .grupo-titulo { display: none; }
      .item { min-height: 42px; padding: 0 12px; }
      .tarjeta-usuario {
        margin-top: 0; margin-left: auto; flex-direction: row; align-items: center; gap: 10px;
        padding: 8px 8px 8px 12px; background: rgba(0, 0, 0, 0.22);
      }
      .salir { min-height: 40px; padding: 0 12px; }
      .principal { padding: 28px 16px 40px; }
    }
    @media (max-width: 560px) {
      /* El email arriba a todo el ancho y los dos botones debajo: en una fila no caben a 390 px */
      .tarjeta-usuario { margin-left: 0; flex: 1 1 100%; flex-wrap: wrap; }
      .usuario { flex: 1 1 100%; min-width: 0; }
      .cuenta, .salir { flex: 1 1 0; }
      .tarjeta-usuario .item + .item { margin-top: 0; }
    }
  `,
})
export class Shell {
  protected readonly sesion = inject(Sesion);
  private readonly router = inject(Router);

  protected readonly inicial = computed(() => (this.sesion.usuario()?.email ?? '?').charAt(0).toUpperCase());
  protected readonly rol = computed(() => {
    const rol = this.sesion.usuario()?.rol;
    return rol ? ROLES[rol].toUpperCase() : '';
  });

  async salir(): Promise<void> {
    await this.sesion.salir();
    await this.router.navigate(['/']);
  }
}
