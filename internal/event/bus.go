package event

import "sync"

type EventType string

const (
    WeatherChange   EventType = "weather_change"
    ResourceFound   EventType = "resource_found"
    SocialEncounter EventType = "social_encounter"
    ItemCrafted     EventType = "item_crafted"
    RumorSpread     EventType = "rumor_spread"
)

type Event struct {
    Tick     int64
    Type     EventType
    Location string
    Payload  map[string]interface{}
}

type Bus struct {
    mu          sync.RWMutex
    subscribers map[string][]chan *Event
    scheduled   []*ScheduledEvent
    eventLog    []*Event
}

type ScheduledEvent struct {
    Event *Event
    At    int64
}

func NewBus() *Bus {
    return &Bus{
        subscribers: make(map[string][]chan *Event),
        eventLog:    make([]*Event, 0),
    }
}

func (b *Bus) Subscribe(location string, ch chan *Event) {
    b.mu.Lock()
    defer b.mu.Unlock()
    b.subscribers[location] = append(b.subscribers[location], ch)
}

func (b *Bus) Publish(e *Event) {
    b.mu.Lock()
    b.eventLog = append(b.eventLog, e)
    b.mu.Unlock()
    for _, ch := range b.subscribers[e.Location] {
        select {
        case ch <- e:
        default:
        }
    }
}

func (b *Bus) Schedule(e *Event, atTick int64) {
    b.mu.Lock()
    defer b.mu.Unlock()
    b.scheduled = append(b.scheduled, &ScheduledEvent{Event: e, At: atTick})
}

func (b *Bus) FlushScheduled(currentTick int64) {
    b.mu.Lock()
    var remaining []*ScheduledEvent
    for _, se := range b.scheduled {
        if se.At <= currentTick {
            b.mu.Unlock()
            b.Publish(se.Event)
            b.mu.Lock()
        } else {
            remaining = append(remaining, se)
        }
    }
    b.scheduled = remaining
    b.mu.Unlock()
}

func (b *Bus) GetEventsAt(location string) []*Event {
    b.mu.RLock()
    defer b.mu.RUnlock()
    var result []*Event
    for _, e := range b.eventLog {
        if e.Location == location {
            result = append(result, e)
        }
    }
    return result
}

func (b *Bus) ClearEvents() {
    b.mu.Lock()
    defer b.mu.Unlock()
    b.eventLog = b.eventLog[:0]
}