import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { PROVEEDORES, ProveedorOAuth, ROLES } from '../core/modelos';
import { Sesion } from '../core/sesion';
import { MINIMO_CONTRASENA, coinciden } from '../core/validadores';
import { PanelMfa } from '../ui/panel-mfa';

@Component({
  selector: 'app-cuenta',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, PanelMfa],
  template: `
    <div class="pila">
      <header class="textos">
        <span class="ruta">~/cuenta</span>
        <h1 class="titulo">Mi cuenta</h1>
      </header>

      <div class="columnas">
        @if (sesion.usuario(); as u) {
          <section aria-labelledby="c-datos" class="cristal tarjeta datos-cuenta">
            <div class="identidad">
              <span aria-hidden="true" class="avatar">{{ u.email.charAt(0).toUpperCase() }}</span>
              <div class="nombre">
                <h2 id="c-datos" class="email">{{ u.email }}</h2>
                <span class="pildora rol" [class]="'rol-' + u.rol">{{ rol() }}</span>
              </div>
            </div>
            <dl class="datos">
              <div><dt>Empresa</dt><dd>{{ empresa() }}</dd></div>
              <div><dt>Alta</dt><dd class="mono">{{ u.creado_en | date: 'dd/MM/yyyy' }}</dd></div>
              <div><dt>Estado</dt><dd class="activa"><span aria-hidden="true" class="punto"></span>Activa</dd></div>
            </dl>
            <p class="nota">El rol solo lo puede cambiar un administrador.</p>
          </section>
        }

        @if (sesion.usuario()?.tiene_contrasena === false) {
          <section aria-labelledby="c-pass" class="cristal tarjeta seguridad">
            <div class="textos-seguridad">
              <span class="etiqueta-mono">SEGURIDAD</span>
              <h2 id="c-pass" class="titulo-2 grande">Sin contraseña</h2>
            </div>
            <p class="nota">Tu cuenta solo entra con {{ vinculadosTexto() }}. La seguridad de tu acceso es la de esa cuenta: protégela con su propia verificación en dos pasos.</p>
          </section>
        } @else {
        <section aria-labelledby="c-pass" class="cristal tarjeta seguridad">
          <div class="textos-seguridad">
            <span class="etiqueta-mono">SEGURIDAD</span>
            <h2 id="c-pass" class="titulo-2 grande">Cambiar contraseña</h2>
          </div>

          @if (exito()) {
            <div role="status" class="aviso aviso-ok">Contraseña actualizada. Se han cerrado tus sesiones en otros dispositivos.</div>
          }
          @if (error()) {
            <div role="alert" class="aviso" [class.aviso-error]="error()!.codigo !== 429" [class.aviso-oro]="error()!.codigo === 429">
              <span class="codigo">{{ error()!.codigo || 'red' }}</span><span>{{ error()!.texto }}</span>
            </div>
          }

          <form aria-labelledby="c-pass" class="formulario" [formGroup]="form" (ngSubmit)="cambiar()" novalidate>
            <div class="campo">
              <label for="c-actual">Contraseña actual</label>
              <input id="c-actual" type="password" class="entrada" autocomplete="current-password" formControlName="actual" />
            </div>
            <div class="campo">
              <label for="c-nueva">Nueva contraseña</label>
              <input id="c-nueva" type="password" class="entrada" autocomplete="new-password" aria-describedby="c-nueva-ayuda" formControlName="nueva"
                [class.invalida]="form.controls.nueva.touched && form.controls.nueva.invalid" />
              <span id="c-nueva-ayuda" class="ayuda">Mínimo 12 caracteres. Mejor una frase larga que una palabra rebuscada.</span>
            </div>
            <div class="campo">
              <label for="c-repetir">Repetir nueva contraseña</label>
              <input id="c-repetir" type="password" class="entrada" autocomplete="new-password" formControlName="repetir"
                [class.invalida]="form.hasError('noCoinciden')" />
              @if (form.hasError('noCoinciden')) { <span class="error-campo">Las contraseñas no coinciden.</span> }
            </div>
            <div class="pie">
              <span class="ayuda tenue">Al cambiarla se revocan todos tus tokens de refresco.</span>
              <button type="submit" class="btn btn-sangre" [disabled]="form.invalid || enviando()">
                {{ enviando() ? 'Actualizando…' : 'Actualizar contraseña' }}
              </button>
            </div>
          </form>
        </section>
        }
      </div>

      <div class="columnas">
        <app-panel-mfa class="mitad" />

        <section aria-labelledby="c-vinculos" class="cristal tarjeta vinculos mitad">
          <div class="textos-seguridad">
            <span class="etiqueta-mono">ACCESO EXTERNO</span>
            <h2 id="c-vinculos" class="titulo-2 grande">Cuentas vinculadas</h2>
          </div>
          @if (avisoVinculo(); as a) {
            <div [attr.role]="a.ok ? 'status' : 'alert'" class="aviso" [class.aviso-ok]="a.ok" [class.aviso-error]="!a.ok">{{ a.texto }}</div>
          }
          @if (!proveedores().length) {
            <p class="nota">El acceso con Google y GitHub no está configurado en este entorno.</p>
          } @else {
            @if (sesion.usuario()?.tiene_contrasena !== false) {
              <div class="campo">
                <label for="c-vinculo-pass">Contraseña (para vincular)</label>
                <input id="c-vinculo-pass" type="password" class="entrada" autocomplete="current-password" [formControl]="contrasenaVinculo" />
              </div>
            }
            <ul class="lista-vinculos">
              @for (p of proveedores(); track p) {
                <li>
                  <span>{{ nombres[p] }}</span>
                  @if (vinculado(p)) {
                    <button type="button" class="btn compacto btn-suave" [disabled]="ocupado()" (click)="desvincular(p)">Desvincular</button>
                  } @else {
                    <button type="button" class="btn compacto btn-oro" [disabled]="ocupado() || (sesion.usuario()?.tiene_contrasena !== false && contrasenaVinculo.invalid)"
                      (click)="vincular(p)">Vincular</button>
                  }
                </li>
              }
            </ul>
            <p class="nota">Vincular solo se hace desde aquí, con tu sesión abierta: así nadie puede enlazar su cuenta de Google a la tuya.</p>
          }
        </section>
      </div>
    </div>
  `,
  styles: `
    .pila { display: flex; flex-direction: column; gap: 28px; }
    .textos { display: flex; flex-direction: column; gap: 10px; }
    .columnas { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }
    .tarjeta { border-radius: 24px; display: flex; flex-direction: column; gap: 22px; }
    .datos-cuenta { flex: 1 1 300px; padding: 30px; }
    .seguridad {
      flex: 2 1 420px; max-width: 640px; padding: 34px;
      background: linear-gradient(165deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.02) 50%, rgba(224, 30, 60, 0.05));
    }
    .identidad { display: flex; align-items: center; gap: 16px; }
    .avatar {
      width: 64px; height: 64px; flex: none; border-radius: 50%; display: flex; align-items: center; justify-content: center;
      background: linear-gradient(140deg, #d4af6e, #7a5a26); box-shadow: 0 0 30px -6px rgba(212, 175, 110, 0.6);
      color: #1a1008; font-family: var(--serif); font-weight: 600; font-size: 30px;
    }
    .nombre { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .email { font-size: 17px; font-weight: 700; overflow-wrap: anywhere; }
    .rol { align-self: flex-start; padding: 3px 10px; font-weight: 700; }
    .rol-usuario { color: #f1e6e0; background: rgba(241, 230, 224, 0.09); }
    .rol-analista { color: #f0c987; background: rgba(212, 175, 110, 0.16); }
    .rol-gestor { color: #9fe3c9; background: rgba(159, 227, 201, 0.12); }
    .rol-admin { color: #ff7a88; background: rgba(224, 30, 60, 0.18); }
    .datos { margin: 0; display: flex; flex-direction: column; gap: 14px; font-size: 14px; }
    .datos div { display: flex; justify-content: space-between; gap: 12px; }
    .datos dt { color: var(--apagado); }
    .datos dd { margin: 0; }
    .datos dd.mono { font-size: 13px; }
    .activa { display: inline-flex; align-items: center; gap: 8px; color: var(--menta); font-weight: 600; }
    .nota { font-size: 13px; line-height: 1.6; color: var(--tenue); }
    .textos-seguridad { display: flex; flex-direction: column; gap: 6px; }
    .grande { font-size: 34px; }
    .formulario { display: flex; flex-direction: column; gap: 18px; }
    .pie { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; justify-content: space-between; padding-top: 6px; }
    .tenue { color: var(--tenue); max-width: 300px; }
    .mitad { flex: 1 1 380px; }
    .vinculos { padding: 30px; }
    .lista-vinculos { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
    .lista-vinculos li { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-weight: 600; }
    @media (max-width: 720px) { .seguridad, .datos-cuenta, .vinculos { padding: 22px; } }
  `,
})
export class Cuenta implements OnInit {
  private readonly api = inject(Api);
  protected readonly sesion = inject(Sesion);

  protected readonly rol = computed(() => {
    const r = this.sesion.usuario()?.rol;
    return r ? ROLES[r] : '';
  });
  /** El personal de Kaelum no tiene empresa cliente; una cuenta de cliente sin ella está pendiente. */
  protected readonly empresa = computed(() => {
    const u = this.sesion.usuario();
    if (u?.empresa_nombre) return u.empresa_nombre;
    return u?.rol === 'admin' || u?.rol === 'analista' ? 'Kaelum Security (personal)' : 'Pendiente de unirse';
  });
  private readonly router = inject(Router);
  private readonly parametros = inject(ActivatedRoute).snapshot.queryParamMap;
  protected readonly nombres = PROVEEDORES;
  protected readonly proveedores = signal<ProveedorOAuth[]>([]);
  protected readonly ocupado = signal(false);
  protected readonly avisoVinculo = signal<{ ok: boolean; texto: string } | null>(this.avisoInicial());
  protected readonly contrasenaVinculo = inject(FormBuilder).nonNullable.control('', Validators.required);
  protected readonly vinculadosTexto = computed(() =>
    (this.sesion.usuario()?.proveedores ?? []).map((p) => PROVEEDORES[p]).join(' o '),
  );
  protected readonly enviando = signal(false);
  protected readonly exito = signal(false);
  protected readonly error = signal<{ codigo: number; texto: string } | null>(null);

  protected readonly form = inject(FormBuilder).nonNullable.group(
    {
      actual: ['', Validators.required],
      nueva: ['', [Validators.required, Validators.minLength(MINIMO_CONTRASENA), Validators.maxLength(128)]],
      repetir: ['', Validators.required],
    },
    { validators: coinciden('nueva', 'repetir') },
  );

  ngOnInit(): void {
    // Datos frescos: el rol o el estado pueden haber cambiado desde el login
    void this.sesion.cargarUsuario().catch(() => undefined);
    this.api.proveedoresOAuth().then(
      (p) => this.proveedores.set(p),
      () => this.proveedores.set([]),
    );
    // La vuelta de una vinculación deja ?vinculado=… o ?error_vinculo=1: se lee una vez y se quita
    if (this.parametros.keys.length) void this.router.navigate([], { replaceUrl: true });
  }

  private avisoInicial(): { ok: boolean; texto: string } | null {
    const vinculado = this.parametros.get('vinculado') as ProveedorOAuth | null;
    if (vinculado && vinculado in PROVEEDORES) {
      return { ok: true, texto: `${PROVEEDORES[vinculado]} vinculado: ya puedes entrar con esa cuenta.` };
    }
    if (this.parametros.has('error_vinculo')) {
      return { ok: false, texto: 'No se ha podido vincular. Puede que esa cuenta ya esté vinculada a otro usuario o que su email no esté verificado.' };
    }
    return null;
  }

  protected vinculado(p: ProveedorOAuth): boolean {
    return this.sesion.usuario()?.proveedores?.includes(p) ?? false;
  }

  async vincular(p: ProveedorOAuth): Promise<void> {
    this.ocupado.set(true);
    this.avisoVinculo.set(null);
    try {
      const conContrasena = this.sesion.usuario()?.tiene_contrasena !== false;
      const url = await this.api.vincularProveedor(p, conContrasena ? this.contrasenaVinculo.value : null);
      // Navegación completa: el proveedor no es una ruta de la SPA
      window.location.assign(url);
    } catch (e) {
      const c = codigo(e);
      this.avisoVinculo.set({ ok: false, texto: c === 422 ? 'La contraseña no es correcta.' : mensajeGeneral(e) });
      this.ocupado.set(false);
    }
  }

  async desvincular(p: ProveedorOAuth): Promise<void> {
    this.ocupado.set(true);
    this.avisoVinculo.set(null);
    try {
      await this.api.desvincularProveedor(p);
      await this.sesion.cargarUsuario();
      this.avisoVinculo.set({ ok: true, texto: `${PROVEEDORES[p]} desvinculado.` });
    } catch (e) {
      this.avisoVinculo.set({ ok: false, texto: mensajeGeneral(e) });
    } finally {
      this.ocupado.set(false);
    }
  }

  async cambiar(): Promise<void> {
    if (this.form.invalid) return;
    this.enviando.set(true);
    this.exito.set(false);
    this.error.set(null);
    const { actual, nueva } = this.form.getRawValue();
    try {
      await this.api.cambiarContrasena(actual, nueva);
    } catch (e) {
      const c = codigo(e);
      this.error.set({
        codigo: c,
        texto: c === 422 ? 'La contraseña actual no es correcta.' : mensajeGeneral(e),
      });
      this.enviando.set(false);
      return;
    }
    // La API revoca TODOS los refrescos, también el de esta pestaña. Se vuelve a entrar con
    // la contraseña nueva para que la sesión actual siga viva sin pedirla otra vez.
    try {
      const desafio = await this.sesion.entrar(this.sesion.usuario()!.email, nueva);
      if (desafio) {
        // Con MFA hace falta el código: se vuelve a entrar desde el login
        this.sesion.limpiar();
        await this.router.navigate(['/login'], { queryParams: { caducada: 1 } });
        return;
      }
    } catch {
      // Si el login falla (p. ej. 429) la sesión dura hasta que caduque el token de acceso
    }
    this.form.reset();
    this.exito.set(true);
    this.enviando.set(false);
  }
}
