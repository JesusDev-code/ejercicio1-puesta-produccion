import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { ROLES, Rol, Usuario, entradas } from '../core/modelos';
import { Sesion } from '../core/sesion';
import { MINIMO_CONTRASENA, generarContrasena } from '../core/validadores';
import { Cargando, FalloServidor } from '../ui/estados';
import { CambioPagina, Paginador } from '../ui/paginador';
import { Opcion, Selector } from '../ui/selector';

@Component({
  selector: 'app-usuarios',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, Cargando, FalloServidor, Selector, Paginador],
  templateUrl: './usuarios.html',
  styleUrl: './usuarios.css',
})
export class Usuarios implements OnInit {
  private readonly api = inject(Api);
  private readonly sesion = inject(Sesion);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly minimo = MINIMO_CONTRASENA;
  protected readonly opcionesRol: Opcion<Rol>[] = entradas(ROLES).map(([valor, etiqueta]) => ({
    valor,
    etiqueta,
    clase: `rol-${valor}`,
  }));
  protected readonly opcionesFiltroRol: Opcion<Rol | ''>[] = [
    { valor: '', etiqueta: 'Todos' },
    ...this.opcionesRol,
  ];

  // --- Listado ---
  protected readonly filtros = this.fb.group({ email: '', rol: '' as Rol | '' });
  protected readonly filas = signal<Usuario[]>([]);
  protected readonly total = signal(0);
  protected readonly desplazamiento = signal(0);
  protected readonly limite = signal(10);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);
  protected readonly ocupado = signal<number | null>(null);
  /** Se incrementa cuando una acción falla: fuerza a repintar las filas con el valor real. */
  protected readonly revision = signal(0);
  protected readonly aviso = signal<{ ok: boolean; texto: string } | null>(null);
  private readonly miId = computed(() => this.sesion.usuario()?.id);

  // --- Alta ---
  protected readonly creando = signal(false);
  protected readonly enviandoAlta = signal(false);
  protected readonly errorAlta = signal<string | null>(null);
  protected readonly verAlta = signal(false);
  protected readonly alta = this.fb.group({
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    rol: ['usuario' as Rol, Validators.required],
    contrasena: ['', [Validators.required, Validators.minLength(MINIMO_CONTRASENA), Validators.maxLength(128)]],
  });

  // --- Restablecer contraseña ---
  private readonly dialogo = viewChild.required<ElementRef<HTMLDialogElement>>('dialogo');
  protected readonly objetivo = signal<Usuario | null>(null);
  protected readonly enviandoReset = signal(false);
  protected readonly errorReset = signal<string | null>(null);
  protected readonly verReset = signal(false);
  protected readonly nuevaContrasena = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.minLength(MINIMO_CONTRASENA), Validators.maxLength(128)],
  });

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
        limite: this.limite(),
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

  paginar({ desplazamiento, limite }: CambioPagina): void {
    this.desplazamiento.set(desplazamiento);
    this.limite.set(limite);
    void this.cargar();
  }

  // --- Alta de cuentas ---

  abrirAlta(): void {
    this.alta.reset();
    this.errorAlta.set(null);
    this.verAlta.set(false);
    this.creando.set(true);
  }

  generarAlta(): void {
    this.alta.controls.contrasena.setValue(generarContrasena());
    this.verAlta.set(true);
  }

  async crear(): Promise<void> {
    if (this.alta.invalid) {
      this.alta.markAllAsTouched();
      return;
    }
    this.enviandoAlta.set(true);
    this.errorAlta.set(null);
    try {
      const nuevo = await this.api.crearUsuario(this.alta.getRawValue());
      this.creando.set(false);
      this.aviso.set({
        ok: true,
        texto: `Cuenta ${nuevo.email} creada como ${ROLES[nuevo.rol].toLowerCase()}. Pásale la contraseña por un canal seguro: podrá cambiarla en Mi cuenta.`,
      });
      this.desplazamiento.set(0);
      await this.cargar();
    } catch (e) {
      this.errorAlta.set(
        codigo(e) === 409
          ? 'Ese email ya tiene cuenta.'
          : codigo(e) === 422
            ? 'Revisa el email y la contraseña (mínimo 12 caracteres).'
            : mensajeGeneral(e),
      );
    } finally {
      this.enviandoAlta.set(false);
    }
  }

  // --- Rol y activación ---

  async cambiarRol(u: Usuario, rol: Rol): Promise<void> {
    if (rol === u.rol) return;
    await this.ejecutar(
      u,
      () => this.api.cambiarRol(u.id, rol),
      `${u.email} ahora es ${ROLES[rol].toLowerCase()}. Sus sesiones abiertas se han cerrado.`,
    );
  }

  async cambiarActivo(u: Usuario): Promise<void> {
    await this.ejecutar(
      u,
      () => this.api.cambiarActivo(u.id, !u.activo),
      u.activo ? `${u.email} ya no puede entrar.` : `${u.email} puede volver a entrar.`,
    );
  }

  private async ejecutar(u: Usuario, fn: () => Promise<Usuario>, exito: string): Promise<void> {
    this.ocupado.set(u.id);
    this.aviso.set(null);
    try {
      const actualizado = await fn();
      this.filas.update((lista) => lista.map((x) => (x.id === actualizado.id ? actualizado : x)));
      this.aviso.set({ ok: true, texto: exito });
    } catch (e) {
      this.revision.update((r) => r + 1);
      this.aviso.set({ ok: false, texto: mensajeGeneral(e) });
    } finally {
      this.ocupado.set(null);
    }
  }

  // --- Restablecer contraseña ---

  abrirReset(u: Usuario): void {
    this.objetivo.set(u);
    this.nuevaContrasena.reset();
    this.errorReset.set(null);
    this.verReset.set(false);
    this.dialogo().nativeElement.showModal();
  }

  cerrarReset(): void {
    this.dialogo().nativeElement.close();
  }

  generarReset(): void {
    this.nuevaContrasena.setValue(generarContrasena());
    this.verReset.set(true);
  }

  async restablecer(): Promise<void> {
    const u = this.objetivo();
    if (!u || this.nuevaContrasena.invalid) return;
    this.enviandoReset.set(true);
    this.errorReset.set(null);
    try {
      await this.api.restablecerContrasena(u.id, this.nuevaContrasena.value);
      this.cerrarReset();
      this.aviso.set({
        ok: true,
        texto: `Contraseña de ${u.email} restablecida. Sus sesiones abiertas se han cerrado.`,
      });
    } catch (e) {
      this.errorReset.set(mensajeGeneral(e));
    } finally {
      this.enviandoReset.set(false);
    }
  }

  async copiar(texto: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(texto);
    } catch {
      // Sin permiso de portapapeles: la contraseña sigue visible para copiarla a mano
    }
  }
}
