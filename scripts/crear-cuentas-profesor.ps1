# Crea (o restablece) las cuentas de prueba del profesor, una por rol, en la API de producción.
#
# - Pide la contraseña de admin sin mostrarla y no la guarda en ningún sitio.
# - Genera una contraseña aleatoria por cuenta con el generador criptográfico del sistema.
# - Escribe CREDENCIALES-PROFESOR.md en la raíz del repo, que está en .gitignore: nunca se sube.
# - Se puede repetir: si una cuenta ya existe, le restablece la contraseña (y cierra sus sesiones).
#
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\crear-cuentas-profesor.ps1

$ErrorActionPreference = 'Stop'
$Web = 'https://ejercicios-de-ciberseguridad-apiincident-d84d64-51-77-145-58.sslip.io'
$Api = "$Web/api"
$Salida = Join-Path (Split-Path $PSScriptRoot -Parent) 'CREDENCIALES-PROFESOR.md'

$Empresa = @{ codigo = 'evaluacion-profesor'; nombre = 'Empresa de evaluación'; sector = 'Evaluación' }
$Cuentas = @(
    @{ email = 'profesor.admin@example.com';    rol = 'admin';    conEmpresa = $false }
    @{ email = 'profesor.analista@example.com'; rol = 'analista'; conEmpresa = $false }
    @{ email = 'profesor.gestor@example.com';   rol = 'gestor';   conEmpresa = $true }
    @{ email = 'profesor.usuario@example.com';  rol = 'usuario';  conEmpresa = $true }
)

function Nueva-Contrasena([int]$Longitud = 20) {
    # Sin caracteres que se confunden al leerla (0/O, 1/l/I). Se descartan los bytes del final
    # del rango para que todos los símbolos sean equiprobables
    $alfabeto = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789-_.'
    $limite = 256 - (256 % $alfabeto.Length)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $resultado = ''
    $byte = New-Object byte[] 1
    while ($resultado.Length -lt $Longitud) {
        $rng.GetBytes($byte)
        if ($byte[0] -lt $limite) { $resultado += $alfabeto[$byte[0] % $alfabeto.Length] }
    }
    $rng.Dispose()
    return $resultado
}

function Llamar($Metodo, $Ruta, $Cuerpo = $null) {
    $parametros = @{ Method = $Metodo; Uri = "$Api$Ruta"; Headers = $script:Cabeceras; ContentType = 'application/json; charset=utf-8' }
    if ($null -ne $Cuerpo) { $parametros.Body = [System.Text.Encoding]::UTF8.GetBytes(($Cuerpo | ConvertTo-Json -Compress)) }
    return Invoke-RestMethod @parametros
}

function Codigo-Http($Fallo) {
    if ($Fallo.Exception.Response) { return [int]$Fallo.Exception.Response.StatusCode }
    return 0
}

# --- Login del admin (la contraseña solo vive en memoria mientras dura el script) ---
$emailAdmin = Read-Host 'Email de tu cuenta admin'
$seguro = Read-Host 'Contraseña de admin' -AsSecureString
$puntero = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
try {
    $claro = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($puntero)
    $login = Invoke-RestMethod -Method Post -Uri "$Api/auth/login" -ContentType 'application/json' `
        -Body (@{ email = $emailAdmin; contrasena = $claro } | ConvertTo-Json -Compress)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($puntero)
    $claro = $null
}
$script:Cabeceras = @{ Authorization = "Bearer $($login.token_acceso)" }
Write-Host 'Sesión de admin iniciada.' -ForegroundColor Green

# --- Empresa de evaluación (la del gestor y el usuario) ---
try {
    $empresa = Llamar Post '/empresas' $Empresa
    Write-Host "Empresa creada: $($empresa.nombre)"
} catch {
    if ((Codigo-Http $_) -ne 409) { throw }
    $empresa = (Llamar Get '/empresas?limite=100').elementos | Where-Object { $_.codigo -eq $Empresa.codigo }
    if (-not $empresa) { throw "Ya hay una empresa con ese nombre pero otro código: revisa Clientes" }
    Write-Host "La empresa ya existía: $($empresa.nombre)"
}

# --- Cuentas ---
$filas = @()
foreach ($c in $Cuentas) {
    $contrasena = Nueva-Contrasena
    $alta = @{ email = $c.email; contrasena = $contrasena; rol = $c.rol }
    if ($c.conEmpresa) { $alta.empresa_id = $empresa.id }
    try {
        $null = Llamar Post '/usuarios' $alta
        Write-Host "Creada: $($c.email) ($($c.rol))"
    } catch {
        if ((Codigo-Http $_) -ne 409) { throw }
        # Ya existía: se le pone la contraseña nueva (la API cierra sus sesiones abiertas)
        $existente = (Llamar Get "/usuarios?email=$([uri]::EscapeDataString($c.email))").elementos |
            Where-Object { $_.email -eq $c.email }
        $null = Llamar Patch "/usuarios/$($existente.id)/contrasena" @{ contrasena_nueva = $contrasena }
        Write-Host "Ya existía, contraseña restablecida: $($c.email)"
    }
    $filas += "| ``$($c.rol)`` | ``$($c.email)`` | ``$contrasena`` |"
    $contrasena = $null
}

# Código vigente, por si se regeneró en una ejecución anterior
$empresa = Llamar Get "/empresas/$($empresa.id)"

# --- Documento (en .gitignore) ---
$fecha = Get-Date -Format 'yyyy-MM-dd HH:mm'
$documento = @"
# Cuentas de prueba para la evaluación

> **Confidencial.** Este archivo está en ``.gitignore`` y no se sube al repositorio. Generado el $fecha.
> Si se filtra, basta con volver a ejecutar ``scripts/crear-cuentas-profesor.ps1``: genera
> contraseñas nuevas y cierra las sesiones abiertas de estas cuentas.

**Aplicación:** $Web

| Rol | Email | Contraseña |
|---|---|---|
$($filas -join "`n")

## Qué ve cada rol

- **admin** (personal de Kaelum): todo. Panel, eventos, sensores, clientes, usuarios y auditoría.
- **analista** (personal de Kaelum): las incidencias que se le asignan; cambia su estado y escribe notas internas.
- **gestor** (responsable de *$($empresa.nombre)*): todas las incidencias de su empresa; en *Equipo e invitaciones*, el código de invitación, su equipo y sus sensores.
- **usuario** (trabajador de *$($empresa.nombre)*): solo las incidencias que él reporta.

## Probar el registro

1. En la pantalla de acceso, **Crear cuenta** con cualquier email y una contraseña de 12 caracteres o más.
2. Al entrar, la cuenta está pendiente y solo ve **Unirme a mi empresa**.
3. Código de invitación de *$($empresa.nombre)*: ``$($empresa.codigo_invitacion)`` (el gestor puede regenerarlo; entonces este deja de valer).
"@
[System.IO.File]::WriteAllText($Salida, $documento, (New-Object System.Text.UTF8Encoding $false))
Write-Host "`nListo. Credenciales en: $Salida" -ForegroundColor Green
Write-Host 'Ese archivo NO se sube a GitHub (está en .gitignore).'
