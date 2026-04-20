from ultralytics import YOLO

model = YOLO("yolo26n.pt")

model.train(
    # --- Пути и железо ---
    data="dataset.yaml",
    epochs=200,
    imgsz=224,
    multi_scale=0.25
    device=[0, 1],
    # sync_bn=True,  'sync_bn' is not a valid YOLO argument.
    workers=4,
    cache="ram",
    time=8,
    save_period=5,
    #
    #
    # --- Оптимизатор (Fine-tuned AdamW) ---
    optimizer="AdamW",
    lr0=0.001,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    warmup_epochs=5.0,
    warmup_momentum=0.8,
    #
    #
    # --- Настройки потерь (Loss) ---
    label_smoothing=0.1,
    cls=1.25,
    box=7.5,
    #
    #
    # --- Аугментации (Геометрия) ---
    mosaic=0.0,
    mixup=0.0,
    fliplr=0.0,
    flipud=0.0,
    degrees=0.0,
    scale=0.0,
    shear=0.0,
    perspective=0.0,
    rect=False,  # WARNING ⚠️ 'rect=True' is incompatible with Multi-GPU training, setting 'rect=False'
    #
    #
    # --- Аугментации (Цвет и Шум) ---
    hsv_h=0.0,
    hsv_s=0.0,
    hsv_v=0.0,
    # blur=0.05,  SyntaxError: 'blur' is not a valid YOLO argument.
    erasing=0.0,
    #
    #
    # --- Валидация и сохранение ---
    batch=256,
    patience=25,
    save=True,
    val=True,
    project="captcha_solver",
    name="yolo26n_v3_50k",
)
