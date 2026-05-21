// frontend/src/lib/permissions.ts
export enum Permission {
  EXECUTE_MEASUREMENTS = 'EXECUTE_MEASUREMENTS',
  EXECUTE_PACKING = 'EXECUTE_PACKING',
  MANAGE_PRODUCTS = 'MANAGE_PRODUCTS',
  MANAGE_USERS = 'MANAGE_USERS',
  MANAGE_SETTINGS = 'MANAGE_SETTINGS',
}

export const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  worker: [
    Permission.EXECUTE_MEASUREMENTS,
    Permission.EXECUTE_PACKING,
  ],
  admin: [
    Permission.EXECUTE_MEASUREMENTS,
    Permission.EXECUTE_PACKING,
    Permission.MANAGE_PRODUCTS,
    Permission.MANAGE_USERS,
    Permission.MANAGE_SETTINGS,
  ],
};

export function hasPermission(role: string | undefined, permission: Permission): boolean {
  if (!role) return false;
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false;
}