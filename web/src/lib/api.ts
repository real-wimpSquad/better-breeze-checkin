const API_BASE =
	import.meta.env.VITE_API_BASE || `http://${window.location.hostname}:8000`;

export interface Person {
	id: string;
	first_name: string;
	last_name: string;
	force_first_name?: string;
	role_name?: string;
}

export interface Event {
	id: string;
	name: string;
	start_datetime: string;
}

export interface CheckinPerson {
	person_id: string;
	name: string;
	code: string;
}

export interface LabelData {
	name: string;
	code: string;
	extra: string;
}

export interface PrinterStatus {
	connected: boolean;
}

async function api<T>(endpoint: string, options?: RequestInit): Promise<T> {
	const resp = await fetch(`${API_BASE}${endpoint}`, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options?.headers
		}
	});

	if (!resp.ok) {
		const error = await resp.text();
		throw new Error(error || `API error: ${resp.status}`);
	}

	return resp.json();
}

export async function getEvents(): Promise<{ events: Event[] }> {
	return api('/events');
}

export async function getEligiblePeople(instanceId: string): Promise<{ people: Person[] }> {
	return api(`/events/${instanceId}/eligible`);
}

export async function getAttendance(instanceId: string): Promise<{ attendance: Person[] }> {
	return api(`/events/${instanceId}/attendance`);
}

export async function checkinBatch(
	instanceId: string,
	people: CheckinPerson[],
	extraLabels: LabelData[] = [],
	printLabels = true
): Promise<{
	results: Array<{ person_id: string; success: boolean; error?: string }>;
	labels_printed: number;
}> {
	return api('/checkin/batch', {
		method: 'POST',
		body: JSON.stringify({
			instance_id: instanceId,
			people,
			extra_labels: extraLabels,
			print_labels: printLabels
		})
	});
}

export async function checkout(
	instanceId: string,
	personId: string
): Promise<{ success: boolean }> {
	return api(`/checkout?instance_id=${instanceId}&person_id=${personId}`, {
		method: 'POST'
	});
}

export async function getPrinterStatus(): Promise<PrinterStatus> {
	return api('/printer/status');
}

export async function getFamily(personId: string): Promise<{ family: Person[] }> {
	return api(`/people/${personId}/family`);
}

export function getDisplayName(person: Person): string {
	const firstName = person.force_first_name || person.first_name;
	return `${firstName} ${person.last_name}`;
}
