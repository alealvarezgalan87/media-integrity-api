# Autenticación

El sistema soporta dos métodos de autenticación que pueden usarse indistintamente.

## Métodos de Autenticación

```mermaid
graph LR
    subgraph "Método 1: Session API Key"
        L[POST /auth/login/] -->|username + password| SK[API Key efímera<br/>sk-... TTL 24h]
        SK -->|X-API-Key header| API1[API Protegida]
    end

    subgraph "Método 2: JWT Bearer"
        T[POST /token/] -->|username + password| JWT[Access Token 1h<br/>+ Refresh Token 7d]
        JWT -->|Authorization: Bearer| API2[API Protegida]
    end
```

## 1. Session API Key (Recomendado para Frontend)

Diseñado para el frontend React. Crea una API Key efímera vinculada al usuario.

### Flujo Completo

```mermaid
sequenceDiagram
    actor U as Usuario
    participant FE as Frontend
    participant API as API
    participant DB as Database

    U->>FE: Ingresar credenciales
    FE->>API: POST /api/v1/auth/login/<br/>{username, password}
    API->>DB: authenticate()
    API->>DB: Crear ApiKey (TTL 24h)
    API-->>FE: {api_key: "sk-...", user: {...}}
    FE->>FE: Guardar api_key en memoria

    Note over FE,API: Requests subsecuentes

    FE->>API: GET /api/v1/audits/<br/>X-API-Key: sk-...
    API->>DB: Buscar key_hash, validar expiry
    API-->>FE: 200 OK {results: [...]}

    Note over FE,API: Logout

    FE->>API: POST /api/v1/auth/logout/<br/>X-API-Key: sk-...
    API->>DB: DELETE ApiKey
    API-->>FE: {detail: "Session destroyed."}
```

### Características

- **TTL**: 24 horas desde la creación
- **Formato**: `sk-{random_urlsafe_32}` (e.g., `sk-a1b2c3d4...`)
- **Almacenamiento**: Solo se guarda el hash SHA-256 en DB
- **Scopes**: `["session"]` para keys de sesión
- **Auto-org**: Si el usuario no tiene organización, se crea una personal automáticamente
- **Cleanup**: Keys expiradas se eliminan al intentar autenticar

### Uso

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'

# Usar API Key
curl http://localhost:8000/api/v1/audits/ \
  -H "X-API-Key: sk-abc123..."

# Logout
curl -X POST http://localhost:8000/api/v1/auth/logout/ \
  -H "X-API-Key: sk-abc123..."
```

## 2. JWT Bearer (Para Integraciones)

Autenticación stateless usando JSON Web Tokens. Ideal para integraciones externas.

### Configuración

| Parámetro | Valor |
|-----------|-------|
| Access Token Lifetime | 1 hora |
| Refresh Token Lifetime | 7 días |
| Rotate Refresh Tokens | Sí |
| Header Type | `Bearer` |

### Uso

```bash
# Obtener tokens
curl -X POST http://localhost:8000/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'
# → {"access": "eyJ...", "refresh": "eyJ..."}

# Usar access token
curl http://localhost:8000/api/v1/audits/ \
  -H "Authorization: Bearer eyJ..."

# Refrescar token
curl -X POST http://localhost:8000/api/v1/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJ..."}'
# → {"access": "eyJ...", "refresh": "eyJ..."} (nuevo par)
```

## Backend de Autenticación (api/authentication.py)

El backend `ApiKeyAuthentication` implementa:

1. Lee header `X-API-Key` del request
2. Calcula SHA-256 del key recibido
3. Busca en DB un `ApiKey` activo con ese hash
4. Verifica que no esté expirado (si tiene `expires_at`)
5. Si expiró → elimina el key y retorna 401
6. Actualiza `last_used_at`
7. Retorna `(user, api_key_obj)` como tupla de auth

## Cambio de Contraseña

`POST /api/v1/auth/change-password/` destruye **todas** las sesiones activas del usuario, forzando re-login en todos los dispositivos.

## Permisos

| Permiso | Endpoints |
|---------|-----------|
| `AllowAny` | health, login, token, schema, docs |
| `IsAuthenticated` | audits, settings, red-flags, logout, change-password |
| `IsAdmin` | users (CRUD completo) |

`IsAdmin` verifica que `user.role == "admin"` o `user.is_superuser`.
