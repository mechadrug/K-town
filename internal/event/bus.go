package event

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
    subscribers map[string][]chan *Event
    scheduled   []*ScheduledEvent
}

type ScheduledEvent struct {
    Event *Event
    At    int64
}

func NewBus() *Bus {
    return &Bus{
        subscribers: make(map[string][]chan *Event),
    }
}

func (b *Bus) Subscribe(location string, ch chan *Event) {
    b.subscribers[location] = append(b.subscribers[location], ch)
}

func (b *Bus) Publish(e *Event) {
    for _, ch := range b.subscribers[e.Location] {
        ch <- e
    }
}

func (b *Bus) Schedule(e *Event, atTick int64) {
    b.scheduled = append(b.scheduled, &ScheduledEvent{Event: e, At: atTick})
}

func (b *Bus) FlushScheduled(currentTick int64) {
    var remaining []*ScheduledEvent
    for _, se := range b.scheduled {
        if se.At <= currentTick {
            b.Publish(se.Event)
        } else {
            remaining = append(remaining, se)
        }
    }
    b.scheduled = remaining
}
