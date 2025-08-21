import type { UUID, ID } from './common'

export type ServiceType = 'DINE_IN' | 'TAKEAWAY' | 'DELIVERY'

export interface OrderItemInput {
menu_item: ID
name: string
qty: string
unit_price: string
total: string
}

export interface PlaceOrderInput {
organization: UUID
location: UUID
service_type: ServiceType
items: OrderItemInput[]
}