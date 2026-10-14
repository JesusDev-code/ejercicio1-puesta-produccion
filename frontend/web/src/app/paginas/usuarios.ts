import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { ROLES, Rol, Usuario, entradas } from '../core/modelos';
import { Sesion } from '../core/sesion';
import { Cargando, FalloServidor } from '../ui/estados';

const POR_PAGINA = 20;

@Component({
  selector: 'app-usuarios',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, Cargando, FalloServidor],
  template: `
    <div class="pila">
      <header class="textos">
        <span class="ruta">~/usuarios</span>
        <h1 class="titulo">Usuarios</h1>
        <p class="subtitulo">Gestiona roles y acceso. Cada cambio queda registrado en la auditoría.</p>
      </header>

      @if (aviso(); as a) {
        <div [attr.role]="a.ok ? 'status' : 'alert'" class="aviso" [class.aviso-ok]="a.ok" [class.aviso-error]="!a.ok">{{ a.texto }}</div>
      }

      <section aria-label="Usuarios" class="cristal panel">
        <form role="search" aria-label="Filtros de usuarios" class="filtros" [formGroup]="filtros" (ngSubmit)="aplicar()">
          <div class="campo busqueda">
            <label for="u-buscar">Buscar por email</label>
            <input id="u-buscar" type="search" class="entrada compacta" placeholder="nombre@empresa.com" maxlength="254" formControlName="email" />
          </div>
          <div class="campo">
            <label for="u-rol">Rol</label>
            <select id="u-rol" class="entrada compacta" formControlName="rol">
              <option value="">Todos</option>
              @for (r of roles; track r[0]) { <option [value]="r[0]">{{ r[1] }}</option> }
            </select>
          </div>
          <button type="submit" class="btn btn-oro">Aplicar</button>
        </form>

        @if (cargando()) {
          <app-cargando />
        } @else if (fallo() !== null) {
          <div class="relleno"><app-fallo-servidor [codigo]="fallo()!" (reintentar)="cargar()" /></div>
        } @else if (filas().length === 0) {
          <p class="vacio">Ningún usuario coincide con el filtro.</p>
        } @else {
          <div class="tabla-contenedor">
            <table class="tabla">
              <thead>
                <tr>
                  <th scope="col">USUARIO</th>
                  <th scope="col">ROL</th>
                  <th scope="col">ESTADO</th>
                  <th scope="col">ALTA</th>
                  <th scope="col"><span class="solo-lector">Acciones</span></th>
                </tr>
              </thead>
              <tbody>
                @for (u of filas(); track u.id) {
                  <tr class="fila" [class.inactivo]="!u.activo">
                    <td>
                      <div class="usuario">
                        <span aria-hidden="true" class="avatar" [class]="'av-' + u.rol">{{ u.email.charAt(0).toUpperCase() }}</span>
                        <div class="datos">
                          <span class="email">{{ u.email }}</span>
                          <span class="mono id">#{{ u.id }}{{ esYo(u) ? ' · tú' : '' }}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <label [for]="'rol-' + u.id" class="solo-lector">Rol de {{ u.email }}</label>
                      <select [id]="'rol-' + u.id" class="rol" [class]="'rol-' + u.rol" [disabled]="esYo(u) || ocupado() === u.id"
                        #selector (change)="cambiarRol(u, selector)">
                        @for (r of roles; track r[0]) { <option [value]="r[0]" [selected]="r[0] === u.rol">{{ r[1] }}</option> }
                      </select>
                    </td>
                    <td>
                      <span class="estado" [class.activo]="u.activo"><span aria-hidden="true" class="punto"></span>{{ u.activo ? 'Activo' : 'Desactivado' }}</span>
                    </td>
                    <td class="mono alta">{{ u.creado_en | date: 'dd/MM/yyyy' }}</td>
                    <td class="acciones">
                      @if (!esYo(u)) {
                        <button type="button" class="btn compacto" [class.btn-peligro]="u.activo" [class.btn-menta]="!u.activo"
                          [disabled]="ocupado() === u.id" (click)="cambiarActivo(u)">{{ u.activo ? 'Desactivar' : 'Reactivar' }}</button>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }

        @if (total() > 0) {
          <nav aria-label="Paginación" class="paginacion">
            <span>Mostrando {{ desplazamiento() + 1 }}–{{ desplazamiento() + filas().length }} de {{ total() }}</span>
            <div class="botones">
              <button type="button" class="btn btn-suave" [disabled]="desplazamiento() === 0" (click)="pagina(-1)">← Anterior</button>
              <button type="button" class="btn btn-suave" [disabled]="desplazamiento() + filas().length >= total()" (click)="pagina(1)">Siguiente →</button>
            </div>
          </nav>
        }
      </section>
    </div>
  `,
  styles: `
    .pila { display: flex; flex-direction: column; gap: 28px; }
    .textos { display: flex; flex-direction: column; gap: 10px; }
    .panel { border-radius: 24px; display: flex; flex-direction: column; }
    .busqueda { flex: 2 1 260px; }
    .tabla { min-width: 820px; }
    .tabla td { padding: 12px 14px; }
    .fila.inactivo { opacity: 0.55; }
    .usuario { display: flex; align-items: center; gap: 12px; }
    .avatar {
      width: 34px; height: 34px; flex: none; border-radius: 50%; display: flex; align-items: center; justify-content: center;
      color: #1a1008; font-weight: 700; font-size: 13px;
    }
    .av-usuario { background: linear-gradient(140deg, #e9dcd6, #8e7c82); }
    .av-analista { background: linear-gradient(140deg, #d4af6e, #7a5a26); }
    .av-admin { background: linear-gradient(140deg, #ff7a88, #a80d26); }
    .datos { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .email { font-weight: 600; overflow-wrap: anywhere; }
    .id { font-size: 11px; color: var(--tenue); }
    .rol {
      min-height: 40px; padding: 0 12px; border: 0; border-radius: 999px; font-family: inherit; font-weight: 700;
      font-size: 13px; cursor: pointer;
    }
    .rol:disabled { cursor: not-allowed; }
    .rol:focus-visible { outline: 2px solid #ff3b4e; outline-offset: 3px; }
    .rol-usuario { color: #f1e6e0; background: rgba(241, 230, 224, 0.09); }
    .rol-analista { color: #f0c987; background: rgba(212, 175, 110, 0.16); }
    .rol-admin { color: #ff7a88; background: rgba(224, 30, 60, 0.18); }
    .rol option { background: #140d12; color: var(--texto); }
    .estado { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: var(--apagado); white-space: nowrap; }
    .estado:not(.activo) .punto { box-shadow: none; }
    .estado.activo { color: var(--menta); }
    .alta { font-size: 12px; color: var(--apagado); white-space: nowrap; }
    .acciones { text-align: right; white-space: nowrap; }
    .compacto { min-height: 38px; padding: 0 14px; border-radius: 10px; font-size: 13px; }
    .botones { display: flex; gap: 8px; }
    .relleno { padding: 0 24px 24px; }
    .vacio { padding: 8px 30px 30px; color: var(--apagado); }
  `,
})
export class Usuarios implements OnInit {
  private readonly api = inject(Api);
  private readonly sesion = inject(Sesion);

  protected readonly roles = entradas(ROLES);
  protected readonly filtros = inject(FormBuilder).nonNullable.group({ email: '', rol: '' as Rol | '' });

  protected readonly filas = signal<Usuario[]>([]);
  protected readonly total = signal(0);
  protected readonly desplazamiento = signal(0);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);
  protected readonly ocupado = signal<number | null>(null);
  protected readonly aviso = signal<{ ok: boolean; texto: string } | null>(null);

  private readonly miId = computed(() => this.sesion.usuario()?.id);

  ngOnInit(): void {
    void this.cargar();
  }

  protected esYo(u: Usuario): boolean {
    return u.id === this.miId();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      const v = this.filtros.getRawValue();
      const pagina = await this.api.usuarios({
        email: v.email.trim(),
        rol: v.rol,
        limite: POR_PAGINA,
        desplazamiento: this.desplazamiento(),
      });
      this.filas.set(pagina.elementos);
      this.total.set(pagina.total);
    } catch (e) {
      this.fallo.set(codigo(e));
    } finally {
      this.cargando.set(false);
    }
  }

  aplicar(): void {
    this.desplazamiento.set(0);
    void this.cargar();
  }

  pagina(direccion: 1 | -1): void {
    this.desplazamiento.update((d) => Math.max(0, d + direccion * POR_PAGINA));
    void this.cargar();
  }

  private reemplazar(actualizado: Usuario): void {
    this.filas.update((lista) => lista.map((u) => (u.id === actualizado.id ? actualizado : u)));
  }

  async cambiarRol(u: Usuario, selector: HTMLSelectElement): Promise<void> {
    const rol = selector.value as Rol;
    if (rol === u.rol) return;
    const ok = await this.ejecutar(
      u,
      () => this.api.cambiarRol(u.id, rol),
      `${u.email} ahora es ${ROLES[rol].toLowerCase()}.`,
    );
    // El enlace [selected] no cambia si el rol no cambió: se devuelve el <select> a mano
    if (!ok) selector.value = u.rol;
  }

  async cambiarActivo(u: Usuario): Promise<void> {
    await this.ejecutar(
      u,
      () => this.api.cambiarActivo(u.id, !u.activo),
      u.activo ? `${u.email} ya no puede entrar.` : `${u.email} puede volver a entrar.`,
    );
  }

  private async ejecutar(u: Usuario, fn: () => Promise<Usuario>, exito: string): Promise<boolean> {
    this.ocupado.set(u.id);
    this.aviso.set(null);
    try {
      this.reemplazar(await fn());
      this.aviso.set({ ok: true, texto: exito });
      return true;
    } catch (e) {
      this.aviso.set({ ok: false, texto: mensajeGeneral(e) });
      return false;
    } finally {
      this.ocupado.set(null);
    }
  }
}
