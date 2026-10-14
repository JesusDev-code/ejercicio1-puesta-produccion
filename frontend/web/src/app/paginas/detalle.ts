import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import {
  CATEGORIAS,
  Categoria,
  Estado,
  Incidente,
  ORDEN_ESTADOS,
  ESTADOS,
  TRANSICIONES,
  Usuario,
  codigoInc,
  entradas,
} from '../core/modelos';
import { Sesion } from '../core/sesion';
import { Cargando, FalloServidor, NoExiste } from '../ui/estados';
import { PildoraEstado, PildoraSeveridad } from '../ui/pildoras';

type Seccion = 'editar' | 'notas' | 'estado' | 'asignar' | 'borrar';

const ETIQUETAS_TRANSICION: Record<Estado, string> = {
  abierto: '↺ Reabrir incidente',
  en_analisis: 'Pasar a en análisis →',
  resuelto: 'Marcar como resuelto →',
  cerrado: 'Cerrar incidente →',
};

const AYUDAS_ESTADO: Record<Estado, string> = {
  abierto: 'Pasar a en análisis exige un analista asignado.',
  en_analisis: 'Las transiciones no permitidas se rechazan.',
  resuelto: 'Una vez cerrado, solo un administrador puede reabrir.',
  cerrado: 'Reabrir queda registrado en la auditoría.',
};

@Component({
  selector: 'app-detalle',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, DatePipe, PildoraEstado, PildoraSeveridad, Cargando, NoExiste, FalloServidor],
  templateUrl: './detalle.html',
  styleUrl: './detalle.css',
})
export class Detalle implements OnInit {
  /** Parámetro de ruta `:id` (withComponentInputBinding). */
  readonly id = input.required<string>();

  private readonly api = inject(Api);
  private readonly sesion = inject(Sesion);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly categorias = entradas(CATEGORIAS);
  protected readonly codigoInc = codigoInc;

  protected nombreCategoria(c: Categoria): string {
    return CATEGORIAS[c];
  }

  protected readonly inc = signal<Incidente | null>(null);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);
  protected readonly ocupado = signal<Seccion | null>(null);
  protected readonly avisos = signal<Partial<Record<Seccion, { ok: boolean; texto: string }>>>({});
  protected readonly editando = signal(false);
  protected readonly confirmandoBorrado = signal(false);
  protected readonly analistas = signal<Usuario[]>([]);

  protected readonly edicion = this.fb.group({
    titulo: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(120)]],
    descripcion: ['', [Validators.required, Validators.maxLength(5000)]],
    categoria: ['otro' as Categoria],
  });
  protected readonly notas = new FormControl('', { nonNullable: true, validators: Validators.maxLength(10000) });
  protected readonly analistaElegido = new FormControl<number | null>(null);

  // --- Qué ve cada rol (la API decide; esto solo oculta) ---

  private readonly yo = computed(() => this.sesion.usuario());
  protected readonly esAdmin = computed(() => this.yo()?.rol === 'admin');
  protected readonly esReportante = computed(() => this.inc()?.reportante_id === this.yo()?.id);
  protected readonly esAnalistaAsignado = computed(
    () => this.yo()?.rol === 'analista' && this.inc()?.analista_id === this.yo()?.id,
  );
  protected readonly gestiona = computed(() => this.esAdmin() || this.esAnalistaAsignado());
  protected readonly puedeEditar = computed(
    () => this.esAdmin() || (this.esReportante() && this.inc()?.estado === 'abierto'),
  );
  protected readonly bloqueado = computed(
    () => !this.esAdmin() && this.esReportante() && this.inc()?.estado !== 'abierto',
  );

  protected readonly siguiente = computed<Estado | null>(() => {
    const estado = this.inc()?.estado;
    if (!estado) return null;
    if (estado === 'cerrado' && !this.esAdmin()) return null;
    return TRANSICIONES[estado];
  });
  protected readonly etiquetaSiguiente = computed(() => {
    const s = this.siguiente();
    return s ? ETIQUETAS_TRANSICION[s] : '';
  });
  protected readonly ayudaEstado = computed(() => {
    const estado = this.inc()?.estado;
    if (!estado) return '';
    if (estado === 'cerrado' && !this.esAdmin()) return 'Solo un administrador puede reabrir.';
    return AYUDAS_ESTADO[estado];
  });

  protected readonly pasos = computed(() => {
    const actual = ORDEN_ESTADOS.indexOf(this.inc()?.estado ?? 'abierto');
    return ORDEN_ESTADOS.map((e, i) => ({
      nombre: ESTADOS[e].nombre,
      fase: i < actual ? 'hecho' : i === actual ? 'actual' : 'pendiente',
      prefijo: i < actual ? '✓' : i === actual ? '●' : '○',
    }));
  });

  protected readonly reportante = computed(() =>
    this.esReportante() ? 'Tú' : (this.inc()?.reportante_email ?? `#${this.inc()?.reportante_id}`),
  );
  protected readonly analista = computed(() => {
    const i = this.inc();
    if (!i?.analista_id) return 'Sin asignar';
    return i.analista_id === this.yo()?.id ? 'Tú' : (i.analista_email ?? `#${i.analista_id}`);
  });

  ngOnInit(): void {
    void this.cargar();
    if (this.esAdmin()) void this.cargarAnalistas();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      this.mostrar(await this.api.incidente(Number(this.id())));
    } catch (e) {
      this.fallo.set(codigo(e));
    } finally {
      this.cargando.set(false);
    }
  }

  private mostrar(inc: Incidente): void {
    this.inc.set(inc);
    this.notas.setValue(inc.notas_internas ?? '');
    this.analistaElegido.setValue(inc.analista_id);
  }

  private async cargarAnalistas(): Promise<void> {
    try {
      const pagina = await this.api.usuarios({ rol: 'analista', limite: 100 });
      this.analistas.set(pagina.elementos.filter((u) => u.activo));
    } catch {
      this.analistas.set([]);
    }
  }

  /** Ejecuta una acción de una sección y deja su resultado (o el error de la API) en ella. */
  private async accion(seccion: Seccion, fn: () => Promise<void>, exito?: string): Promise<void> {
    this.ocupado.set(seccion);
    this.avisos.update((a) => ({ ...a, [seccion]: undefined }));
    try {
      await fn();
      if (exito) this.avisos.update((a) => ({ ...a, [seccion]: { ok: true, texto: exito } }));
    } catch (e) {
      if (codigo(e) === 404) {
        this.fallo.set(404);
        return;
      }
      const texto =
        codigo(e) === 422 ? 'Hay campos por revisar.' : mensajeGeneral(e);
      this.avisos.update((a) => ({ ...a, [seccion]: { ok: false, texto } }));
    } finally {
      this.ocupado.set(null);
    }
  }

  empezarEdicion(): void {
    const i = this.inc()!;
    this.edicion.setValue({ titulo: i.titulo, descripcion: i.descripcion, categoria: i.categoria });
    this.editando.set(true);
  }

  guardarEdicion(): Promise<void> {
    const i = this.inc()!;
    const v = this.edicion.getRawValue();
    // Solo se envía lo que ha cambiado
    const cambios = Object.fromEntries(
      Object.entries(v).filter(([k, valor]) => i[k as keyof typeof v] !== valor),
    );
    if (!Object.keys(cambios).length) {
      this.editando.set(false);
      return Promise.resolve();
    }
    return this.accion('editar', async () => {
      this.mostrar(await this.api.editarIncidente(i.id, cambios));
      this.editando.set(false);
    });
  }

  guardarNotas(): Promise<void> {
    return this.accion(
      'notas',
      async () => this.mostrar(await this.api.guardarNotas(this.inc()!.id, this.notas.value)),
      'Notas guardadas.',
    );
  }

  avanzar(): Promise<void> {
    const destino = this.siguiente();
    if (!destino) return Promise.resolve();
    return this.accion('estado', async () =>
      this.mostrar(await this.api.cambiarEstado(this.inc()!.id, destino)),
    );
  }

  asignar(): Promise<void> {
    const analista = this.analistaElegido.value;
    if (!analista) return Promise.resolve();
    return this.accion(
      'asignar',
      async () => this.mostrar(await this.api.asignar(this.inc()!.id, Number(analista))),
      'Analista asignado.',
    );
  }

  borrar(): Promise<void> {
    return this.accion('borrar', async () => {
      await this.api.borrarIncidente(this.inc()!.id);
      await this.router.navigate(['/incidentes']);
    });
  }
}
