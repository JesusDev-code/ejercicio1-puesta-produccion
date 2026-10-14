import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { Clientes } from '../core/clientes';
import { codigo, mensajeGeneral } from '../core/errores';
import { Empresa } from '../core/modelos';
import { Cargando, FalloServidor } from '../ui/estados';

const PATRON_CODIGO = /^[a-z0-9]+(-[a-z0-9]+)*$/;

/** «Clínica Solana, S.L.» → «clinica-solana-s-l». Solo una sugerencia: el admin puede cambiarlo. */
function aCodigo(nombre: string): string {
  return nombre
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
    .replace(/-+$/, '');
}

@Component({
  selector: 'app-clientes',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, DatePipe, Cargando, FalloServidor],
  styleUrl: './usuarios.css',
  template: `
    <div class="pila">
      <header class="cabecera">
        <div class="textos">
          <span class="ruta">~/clientes</span>
          <h1 class="titulo">Clientes</h1>
          <p class="subtitulo">
            Las empresas a las que Kaelum da servicio. Cada una ve solo sus incidencias; sus sensores declaran el código para que los eventos le lleguen a ella.
          </p>
        </div>
        @if (!creando()) {
          <button type="button" class="btn btn-sangre" (click)="abrirAlta()"><span aria-hidden="true" class="mas">+</span> Nuevo cliente</button>
        }
      </header>

      @if (aviso(); as a) {
        <div [attr.role]="a.ok ? 'status' : 'alert'" class="aviso" [class.aviso-ok]="a.ok" [class.aviso-error]="!a.ok">
          <span>{{ a.texto }}</span>
          <button type="button" class="cerrar-aviso" aria-label="Cerrar aviso" (click)="aviso.set(null)">×</button>
        </div>
      }

      @if (creando()) {
        <section aria-labelledby="t-alta" class="cristal alta">
          <div class="alta-cabecera">
            <span class="etiqueta-mono">ALTA DE CLIENTE</span>
            <h2 id="t-alta" class="titulo-2">Nuevo cliente</h2>
          </div>

          @if (errorAlta()) {
            <div role="alert" class="aviso aviso-error">{{ errorAlta() }}</div>
          }

          <form class="alta-form" [formGroup]="alta" (ngSubmit)="crear()" novalidate>
            <div class="campo email">
              <label for="c-nombre">Nombre</label>
              <input id="c-nombre" class="entrada" autocomplete="off" placeholder="Transportes Ibarra" formControlName="nombre" (input)="sugerirCodigo()"
                [class.invalida]="alta.controls.nombre.touched && alta.controls.nombre.invalid" />
              @if (alta.controls.nombre.touched && alta.controls.nombre.invalid) {
                <span class="error-campo">Entre 2 y 120 caracteres.</span>
              }
            </div>

            <div class="campo rol">
              <label for="c-sector">Sector</label>
              <input id="c-sector" class="entrada" autocomplete="off" placeholder="Logística" formControlName="sector" />
            </div>

            <div class="campo contrasena">
              <label for="c-codigo">Código</label>
              <input id="c-codigo" class="entrada mono" autocomplete="off" placeholder="transportes-ibarra" formControlName="codigo"
                aria-describedby="c-codigo-ayuda" (input)="codigoTocado = true"
                [class.invalida]="alta.controls.codigo.touched && alta.controls.codigo.invalid" />
              <span id="c-codigo-ayuda" class="ayuda">
                Minúsculas, números y guiones. Es lo que configuran sus sensores (<span class="mono">EMPRESA</span>) y <strong>no se puede cambiar</strong> después.
              </span>
            </div>

            <div class="acciones-alta">
              <button type="submit" class="btn btn-sangre" [disabled]="enviando()">{{ enviando() ? 'Creando…' : 'Crear cliente' }}</button>
              <button type="button" class="btn btn-suave" (click)="creando.set(false)">Cancelar</button>
            </div>
          </form>
        </section>
      }

      <section aria-label="Clientes" class="cristal panel">
        @if (cargando()) {
          <app-cargando />
        } @else if (fallo() !== null) {
          <div class="relleno"><app-fallo-servidor [codigo]="fallo()!" (reintentar)="cargar()" /></div>
        } @else if (clientes.lista().length === 0) {
          <p class="vacio">Todavía no hay clientes. Crea el primero con «Nuevo cliente».</p>
        } @else {
          <div class="tabla-contenedor">
            <table class="tabla">
              <thead>
                <tr>
                  <th scope="col">CLIENTE</th>
                  <th scope="col">SECTOR</th>
                  <th scope="col">ESTADO</th>
                  <th scope="col">ALTA</th>
                  <th scope="col"><span class="solo-lector">Acciones</span></th>
                </tr>
              </thead>
              <tbody>
                @for (e of clientes.lista(); track e.id) {
                  <tr class="fila" [class.inactivo]="!e.activa">
                    <td>
                      <div class="usuario">
                        <span aria-hidden="true" class="avatar av-analista">{{ e.nombre.charAt(0).toUpperCase() }}</span>
                        <div class="datos">
                          <span class="email">{{ e.nombre }}</span>
                          <span class="mono id">{{ e.codigo }}</span>
                        </div>
                      </div>
                    </td>
                    <td>{{ e.sector ?? '—' }}</td>
                    <td>
                      <span class="estado" [class.activo]="e.activa"><span aria-hidden="true" class="punto"></span>{{ e.activa ? 'Activo' : 'De baja' }}</span>
                    </td>
                    <td class="mono alta-fecha">{{ e.creada_en | date: 'dd/MM/yyyy' }}</td>
                    <td class="acciones">
                      <a class="btn compacto btn-suave" [routerLink]="['/usuarios']" [queryParams]="{ empresa: e.id }">Usuarios</a>
                      <button type="button" class="btn compacto btn-suave" [disabled]="ocupado() === e.id" (click)="abrirEdicion(e)">Editar</button>
                      <button type="button" class="btn compacto" [class.btn-peligro]="e.activa" [class.btn-menta]="!e.activa"
                        [disabled]="ocupado() === e.id" (click)="cambiarActiva(e)">{{ e.activa ? 'Dar de baja' : 'Reactivar' }}</button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
    </div>

    <dialog #dialogo class="dialogo" aria-labelledby="t-editar" (close)="objetivo.set(null)">
      @if (objetivo(); as e) {
        <form class="dialogo-form" [formGroup]="edicion" (ngSubmit)="guardar()" novalidate>
          <span class="etiqueta-mono">CLIENTE · <span class="mono">{{ e.codigo }}</span></span>
          <h2 id="t-editar" class="titulo-2">Editar cliente</h2>

          @if (errorEdicion()) {
            <div role="alert" class="aviso aviso-error">{{ errorEdicion() }}</div>
          }

          <div class="campo">
            <label for="e-nombre">Nombre</label>
            <input id="e-nombre" class="entrada" formControlName="nombre" />
          </div>
          <div class="campo">
            <label for="e-sector">Sector</label>
            <input id="e-sector" class="entrada" formControlName="sector" />
          </div>
          <span class="ayuda">El código no se edita: lo usan sus sensores para identificarse.</span>

          <div class="acciones-alta">
            <button type="submit" class="btn btn-sangre" [disabled]="edicion.invalid || ocupado() === e.id">Guardar</button>
            <button type="button" class="btn btn-suave" (click)="cerrarEdicion()">Cancelar</button>
          </div>
        </form>
      }
    </dialog>
  `,
})
export class ClientesPagina implements OnInit {
  private readonly api = inject(Api);
  private readonly fb = inject(FormBuilder).nonNullable;
  protected readonly clientes = inject(Clientes);

  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);
  protected readonly ocupado = signal<number | null>(null);
  protected readonly aviso = signal<{ ok: boolean; texto: string } | null>(null);

  // --- Alta ---
  protected readonly creando = signal(false);
  protected readonly enviando = signal(false);
  protected readonly errorAlta = signal<string | null>(null);
  /** Si el admin escribió el código a mano, deja de sugerirse desde el nombre. */
  protected codigoTocado = false;
  protected readonly alta = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    sector: ['', Validators.maxLength(80)],
    codigo: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(40), Validators.pattern(PATRON_CODIGO)]],
  });

  // --- Edición ---
  private readonly dialogo = viewChild.required<ElementRef<HTMLDialogElement>>('dialogo');
  protected readonly objetivo = signal<Empresa | null>(null);
  protected readonly errorEdicion = signal<string | null>(null);
  protected readonly edicion = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    sector: ['', Validators.maxLength(80)],
  });

  ngOnInit(): void {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      this.clientes.lista.set((await this.api.empresas()).elementos);
    } catch (e) {
      this.fallo.set(codigo(e));
    } finally {
      this.cargando.set(false);
    }
  }

  abrirAlta(): void {
    this.alta.reset();
    this.codigoTocado = false;
    this.errorAlta.set(null);
    this.creando.set(true);
  }

  sugerirCodigo(): void {
    if (!this.codigoTocado) this.alta.controls.codigo.setValue(aCodigo(this.alta.controls.nombre.value));
  }

  async crear(): Promise<void> {
    if (this.alta.invalid) {
      this.alta.markAllAsTouched();
      return;
    }
    this.enviando.set(true);
    this.errorAlta.set(null);
    try {
      const v = this.alta.getRawValue();
      const nueva = await this.api.crearEmpresa({ ...v, sector: v.sector.trim() || null });
      this.clientes.actualizar(nueva);
      this.creando.set(false);
      this.aviso.set({
        ok: true,
        texto: `Cliente ${nueva.nombre} creado. Ya puedes darle usuarios y configurar sus sensores con EMPRESA=${nueva.codigo}.`,
      });
    } catch (e) {
      this.errorAlta.set(codigo(e) === 409 ? 'Ya hay un cliente con ese nombre o ese código.' : mensajeGeneral(e));
    } finally {
      this.enviando.set(false);
    }
  }

  abrirEdicion(e: Empresa): void {
    this.objetivo.set(e);
    this.edicion.setValue({ nombre: e.nombre, sector: e.sector ?? '' });
    this.errorEdicion.set(null);
    this.dialogo().nativeElement.showModal();
  }

  cerrarEdicion(): void {
    this.dialogo().nativeElement.close();
  }

  async guardar(): Promise<void> {
    const e = this.objetivo();
    if (!e || this.edicion.invalid) return;
    this.ocupado.set(e.id);
    this.errorEdicion.set(null);
    try {
      const v = this.edicion.getRawValue();
      // Sector vacío = quitarlo (la API lo interpreta así)
      this.clientes.actualizar(await this.api.editarEmpresa(e.id, { nombre: v.nombre, sector: v.sector.trim() }));
      this.cerrarEdicion();
    } catch (err) {
      this.errorEdicion.set(codigo(err) === 409 ? 'Ya hay un cliente con ese nombre.' : mensajeGeneral(err));
    } finally {
      this.ocupado.set(null);
    }
  }

  async cambiarActiva(e: Empresa): Promise<void> {
    this.ocupado.set(e.id);
    this.aviso.set(null);
    try {
      const actualizada = await this.api.editarEmpresa(e.id, { activa: !e.activa });
      this.clientes.actualizar(actualizada);
      this.aviso.set({
        ok: true,
        texto: actualizada.activa
          ? `${e.nombre} vuelve a estar activo: sus usuarios pueden entrar.`
          : `${e.nombre} dado de baja: sus usuarios ya no pueden entrar y se han cerrado sus sesiones.`,
      });
    } catch (err) {
      this.aviso.set({ ok: false, texto: mensajeGeneral(err) });
    } finally {
      this.ocupado.set(null);
    }
  }
}
