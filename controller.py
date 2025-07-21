class SimpleController:

  def __init__(self):
    self.toggle = False
    self.filter_queue = []

  def update(self, treatment):

    if treatment.reservoir_level < 0.5:
      self.toggle = False

    if treatment.reservoir_level > 0.8:
      self.toggle = True
    
    for i, f in enumerate(treatment.filter_streets[0].filter_volumes):
      if f > 1000 and i not in self.filter_queue:
        self.filter_queue.append(i)

    night = treatment.step % (24*60) < 6*60 or treatment.step % (24*60) > 18*60

    if treatment.reservoir_level > 0.5 and len(self.filter_queue) > 0 and not treatment.backwash_active and treatment.backwash_buffer < 300 and night:
      treatment.start_backwash(0, self.filter_queue.pop(0))
    
    return 100 if self.toggle else 400



