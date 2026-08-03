from ultralytics import YOLO
import argparse
import os

def train_classifier(dataset_path, model_name, epochs=20):
    """
    Trains a YOLOv8 Nano Classification model on a dataset.
    The dataset must be in the standard YOLO classification format:
    dataset/
    ├── train/
    │   ├── class_1/
    │   └── class_2/
    ├── val/
    │   ├── class_1/
    │   └── class_2/
    """
    print(f"\n=======================================================")
    print(f" Training {model_name} on {dataset_path}")
    print(f"=======================================================")
    
    if not os.path.exists(dataset_path):
        print(f"ERROR: Dataset path '{dataset_path}' not found!")
        print("Please download your dataset from Roboflow (Select 'YOLOv8 Classification' format) and unzip it here.")
        return

    # Load a pre-trained nano classification model
    model = YOLO('yolov8n-cls.pt')

    # Train the model
    # imgsz=64 because our crops are very small (fast training & inference)
    results = model.train(
        data=dataset_path,
        epochs=epochs,
        imgsz=64, 
        batch=32,
        project='trained_models',
        name=model_name,
        device='cpu' # Uses Mac CPU/MPS automatically. Change to 'mps' if you want hardware acceleration on Apple Silicon.
    )
    
    print(f"\n[+] Training Complete! Your model is saved at:")
    print(f"    trained_models/{model_name}/weights/best.pt\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLOv8 Classification Models")
    parser.add_argument("--task", type=str, choices=["smile", "thumbs", "all"], default="all", help="Which model to train")
    parser.add_argument("--smile_data", type=str, default="datasets/smile_dataset", help="Path to Roboflow smile dataset")
    parser.add_argument("--thumbs_data", type=str, default="datasets/thumbs_dataset", help="Path to Roboflow thumbs dataset")
    parser.add_argument("--epochs", type=int, default=20, help="Number of epochs to train")
    
    args = parser.parse_args()
    
    if args.task in ["smile", "all"]:
        train_classifier(args.smile_data, "smile_classifier", args.epochs)
        
    if args.task in ["thumbs", "all"]:
        train_classifier(args.thumbs_data, "thumbs_classifier", args.epochs)
